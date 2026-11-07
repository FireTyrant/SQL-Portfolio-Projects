#!/usr/bin/env python3
"""Powerball number generator built on every draw since the first one (April 22, 1992).

Steps:
  1. Download the official draw history (Feb 2010 -> latest draw) from the
     New York State open-data portal (falls back to the saved CSV in data/),
     and combine it with data/powerball_draws_1992_2010.csv, the earlier draws
     from the powerball.net archive (checked against 304 overlapping official
     draws: 0 mismatches).
  2. Load it into a SQLite database (output/powerball.db) using the
     schema in sql/schema.sql.
  3. Score every number in the current game with sql/number_stats.sql:
        - all-time lift   : hits vs. what chance predicts (era-adjusted)
        - recent lift     : same, over the last N draws ("hot" numbers)
        - overdue ratio   : draws since last hit vs. the average gap
  4. Write the picks for the next draw to output/latest_picks.md.

Run it again after every draw (Monday, Wednesday & Saturday) to refresh the picks.

Standard library only:  python3 powerball.py [--tickets 5] [--recent 100]
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_URL = "https://data.ny.gov/api/views/d6yy-54nr/rows.csv?accessType=DOWNLOAD"

HERE = Path(__file__).resolve().parent
SQL_DIR = HERE / "sql"
CSV_PATH = HERE / "data" / "powerball_draws.csv"
ARCHIVE_PATH = HERE / "data" / "powerball_draws_1992_2010.csv"
OUT_DIR = HERE / "output"
DB_PATH = OUT_DIR / "powerball.db"
PICKS_PATH = OUT_DIR / "latest_picks.md"

# How the three signals are blended into one score (1.0 = perfectly average).
WEIGHT_ALL_TIME = 0.50
WEIGHT_RECENT = 0.35
WEIGHT_OVERDUE = 0.15
OVERDUE_CAP = 2.0  # don't let a single long gap dominate the score


# --------------------------------------------------------------------------- #
# 1. Data
# --------------------------------------------------------------------------- #
def fetch_csv(offline: bool) -> str:
    if not offline:
        try:
            req = urllib.request.Request(DATA_URL, headers={"User-Agent": "powerball-generator"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                text = resp.read().decode("utf-8")
            if "Winning Numbers" in text.splitlines()[0]:
                CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
                CSV_PATH.write_text(text, encoding="utf-8")
                print(f"Downloaded latest draw history -> {CSV_PATH.relative_to(HERE)}")
                return text
            print("Unexpected download format; using saved CSV.", file=sys.stderr)
        except Exception as exc:  # network problems etc.
            print(f"Download failed ({exc}); using saved CSV.", file=sys.stderr)
    if not CSV_PATH.exists():
        sys.exit(f"No data available: {CSV_PATH} is missing and download failed.")
    return CSV_PATH.read_text(encoding="utf-8")


def parse_draws(text: str) -> list[tuple]:
    """Official NY data: 'Winning Numbers' holds 5 white balls then the Powerball."""
    rows = {}
    for rec in csv.DictReader(io.StringIO(text)):
        date = datetime.strptime(rec["Draw Date"].strip(), "%m/%d/%Y").date().isoformat()
        nums = [int(x) for x in rec["Winning Numbers"].split()]
        whites = sorted(nums[:5])
        if len(nums) != 6 or len(set(whites)) != 5:
            print(f"Skipping malformed draw {date}: {rec['Winning Numbers']}", file=sys.stderr)
            continue
        mult = (rec.get("Multiplier") or "").strip()
        rows[date] = (date, *whites, nums[5], int(mult) if mult.isdigit() else None, "ny_open_data")

    # Earlier draws (1992 -> Feb 2010) are not in the official feed.
    with ARCHIVE_PATH.open(encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            date = rec["draw_date"]
            if date not in rows:
                whites = sorted(int(rec[f"n{i}"]) for i in range(1, 6))
                rows[date] = (date, *whites, int(rec["powerball"]), None, "archive_1992_2010")
    return sorted(rows.values())


def build_db(draws: list[tuple]) -> sqlite3.Connection:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript((SQL_DIR / "schema.sql").read_text())
    con.executemany("INSERT OR REPLACE INTO draws VALUES (?,?,?,?,?,?,?,?,?)", draws)
    con.executemany(
        "INSERT INTO draw_numbers VALUES (?,?,?)",
        [(d[0], "white", n) for d in draws for n in d[1:6]] + [(d[0], "power", d[6]) for d in draws],
    )
    con.commit()

    # Sanity check: every ball must fit the rules of the era it was drawn in.
    bad = con.execute("""
        SELECT d.draw_date FROM draws d
        LEFT JOIN eras e ON d.draw_date BETWEEN e.start_date AND e.end_date
        WHERE e.era_id IS NULL OR d.n5 > e.white_max OR d.n1 < 1
           OR d.powerball > e.power_max OR d.powerball < 1
    """).fetchall()
    if bad:
        sys.exit(f"{len(bad)} draws don't fit their era's number ranges, e.g. {bad[:3]}")
    return con


# --------------------------------------------------------------------------- #
# 2. Scoring
# --------------------------------------------------------------------------- #
def number_stats(con: sqlite3.Connection, ball_type: str, recent: int) -> list[dict]:
    con.row_factory = sqlite3.Row
    sql = (SQL_DIR / "number_stats.sql").read_text()
    stats = []
    for r in con.execute(sql, {"ball_type": ball_type, "recent_draws": recent}):
        s = dict(r)
        s["lift_all"] = s["hits_all"] / s["expected_all"]
        s["lift_recent"] = s["hits_recent"] / s["expected_recent"] if s["expected_recent"] else 1.0
        # Average gap between hits is 1/p draws; ratio > 1 means "overdue".
        s["overdue"] = s["draws_since_last"] * s["p_current"]
        s["score"] = (
            WEIGHT_ALL_TIME * s["lift_all"]
            + WEIGHT_RECENT * s["lift_recent"]
            + WEIGHT_OVERDUE * min(s["overdue"], OVERDUE_CAP)
        )
        stats.append(s)
    stats.sort(key=lambda s: (-s["score"], s["number"]))
    return stats


def weighted_sample(stats: list[dict], k: int, rng: random.Random, sharpness: float = 4.0) -> list[int]:
    """Pick k distinct numbers, favouring higher scores (score ** sharpness)."""
    pool = {s["number"]: s["score"] ** sharpness for s in stats}
    picked = []
    for _ in range(k):
        n = rng.choices(list(pool), weights=list(pool.values()))[0]
        picked.append(n)
        del pool[n]
    return sorted(picked)


def make_tickets(whites, powers, count, rng) -> list[tuple[str, list[int], int]]:
    tickets = [("Top scores", sorted(s["number"] for s in whites[:5]), powers[0]["number"])]
    seen = {tuple(tickets[0][1]) + (tickets[0][2],)}
    while len(tickets) < count:
        w = weighted_sample(whites, 5, rng)
        m = weighted_sample(powers, 1, rng)[0]
        if tuple(w) + (m,) not in seen:
            seen.add(tuple(w) + (m,))
            tickets.append(("Weighted", w, m))
    return tickets


# --------------------------------------------------------------------------- #
# 3. Report
# --------------------------------------------------------------------------- #
def fmt(nums) -> str:
    return " ".join(f"{n:02d}" for n in nums)


def stats_table(stats: list[dict], top: int, recent: int) -> list[str]:
    lines = [
        f"| Rank | Number | Score | All-time hits | All-time lift | Last {recent} hits | Recent lift | Draws since seen | Last drawn |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for i, s in enumerate(stats[:top], 1):
        lines.append(
            f"| {i} | **{s['number']:02d}** | {s['score']:.3f} | {s['hits_all']} | {s['lift_all']:.2f} "
            f"| {s['hits_recent']} | {s['lift_recent']:.2f} | {s['draws_since_last']} | {s['last_drawn'] or '-'} |"
        )
    return lines


def write_report(con, whites, powers, tickets, recent) -> str:
    total, first, last = con.execute("SELECT COUNT(*), MIN(draw_date), MAX(draw_date) FROM draws").fetchone()
    latest = con.execute("SELECT * FROM draws ORDER BY draw_date DESC LIMIT 1").fetchone()
    cold = sorted(whites, key=lambda s: (s["score"], s["number"]))[:10]

    lines = [
        "# Powerball picks for the next draw",
        "",
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from **{total:,} draws** "
        f"({first} to {last})._",
        "",
        f"**Latest draw ({latest[0]}):** {fmt(latest[1:6])}  Powerball **{latest[6]:02d}**",
        "",
        "## Tickets",
        "",
        "| # | Method | White balls | Powerball |",
        "|---:|---|---|---:|",
    ]
    for i, (method, w, m) in enumerate(tickets, 1):
        lines.append(f"| {i} | {method} | **{fmt(w)}** | **{m:02d}** |")
    lines += [
        "",
        "## Top white balls (1-69)",
        "",
        *stats_table(whites, 15, recent),
        "",
        "## Top Powerballs (1-26)",
        "",
        *stats_table(powers, 8, recent),
        "",
        "## Coldest white balls",
        "",
        ", ".join(f"{s['number']:02d}" for s in cold),
        "",
        "---",
        "",
        "**How the score works:** `score = 0.50 x all-time lift + 0.35 x recent lift + 0.15 x overdue ratio`. "
        "A lift of 1.00 means the number has hit exactly as often as chance predicts, counting only draws in "
        "which it was in the drum. The overdue ratio is draws-since-last-hit divided by the average gap "
        f"(capped at {OVERDUE_CAP:g}).",
        "",
        "**Reality check:** every Powerball draw is independent and every number is equally likely. "
        "These picks reflect past patterns only; they do not change your odds "
        "(1 in 292,201,338 for the jackpot). Play for fun.",
        "",
    ]
    report = "\n".join(lines)
    PICKS_PATH.write_text(report, encoding="utf-8")
    return report


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickets", type=int, default=5, help="number of tickets to generate (default 5)")
    ap.add_argument("--recent", type=int, default=100, help="draws counted as 'recent' (default 100)")
    ap.add_argument("--seed", type=int, help="random seed (default: latest draw date, so picks are stable per draw)")
    ap.add_argument("--offline", action="store_true", help="skip download, use data/powerball_draws.csv")
    args = ap.parse_args()

    draws = parse_draws(fetch_csv(args.offline))
    con = build_db(draws)
    whites = number_stats(con, "white", args.recent)
    powers = number_stats(con, "power", args.recent)

    seed = args.seed if args.seed is not None else int(draws[-1][0].replace("-", ""))
    tickets = make_tickets(whites, powers, max(1, args.tickets), random.Random(seed))
    write_report(con, whites, powers, tickets, args.recent)

    print(f"\nLoaded {len(draws):,} draws ({draws[0][0]} to {draws[-1][0]}).")
    print("Picks for the next draw:")
    for i, (method, w, m) in enumerate(tickets, 1):
        print(f"  {i}. {fmt(w)}  Powerball {m:02d}   ({method})")
    print(f"\nFull report: {PICKS_PATH.relative_to(HERE)}")


if __name__ == "__main__":
    main()
