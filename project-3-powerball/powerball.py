#!/usr/bin/env python3
"""Powerball number generator built on every draw since the first one (April 22, 1992).

Steps:
  1. Download the draw history from powerball.com, the official site
     (only new pages after the first run), saved to data/powerball_official.csv.
     powerball.com lists every draw since 1992 but shows no numbers for the
     577 draws from Apr 1992 to Oct 1997; those come from
     data/powerball_draws_1992_2010.csv (the powerball.net archive, which
     matches all 1,279 official draws it overlaps).
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
import re
import time
import urllib.parse
import random
import sqlite3
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

OFFICIAL_URL = "https://www.powerball.com/previous-results"
FIRST_DRAW = "1992-04-22"
REFETCH_DAYS = 30  # re-download the last month each run, in case of corrections

HERE = Path(__file__).resolve().parent
SQL_DIR = HERE / "sql"
OFFICIAL_CSV_PATH = HERE / "data" / "powerball_official.csv"
ARCHIVE_PATH = HERE / "data" / "powerball_draws_1992_2010.csv"
OUT_DIR = HERE / "output"
DB_PATH = OUT_DIR / "powerball.db"
PICKS_PATH = OUT_DIR / "latest_picks.md"
OFFICIAL_COLUMNS = ["draw_date", "n1", "n2", "n3", "n4", "n5", "powerball", "power_play"]

# How the three signals are blended into one score (1.0 = perfectly average).
WEIGHT_ALL_TIME = 0.50
WEIGHT_RECENT = 0.35
WEIGHT_OVERDUE = 0.15
OVERDUE_CAP = 2.0  # don't let a single long gap dominate the score


# --------------------------------------------------------------------------- #
# 1. Data
# --------------------------------------------------------------------------- #
CARD_RE = re.compile(r'<a class="card"[^>]*date=(\d{4}-\d{2}-\d{2})">(.*?)</a>', re.S)
WHITE_RE = re.compile(r'white-balls[^"]*">\s*<div>\s*(\d+)')
POWER_RE = re.compile(r'col powerball[^"]*">\s*<div>\s*(\d+)')
PLAY_RE = re.compile(r'class="multiplier">(\d+)x')


def fetch_page(start: str, end: str, page: int) -> list[tuple[str, str]]:
    query = urllib.parse.urlencode({"gc": "powerball", "sd": start, "ed": end, "pg": page})
    req = urllib.request.Request(f"{OFFICIAL_URL}?{query}", headers={
        "User-Agent": "powerball-generator", "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return CARD_RE.findall(resp.read().decode("utf-8"))


def parse_card(date: str, html: str) -> dict:
    whites, power, play = WHITE_RE.findall(html), POWER_RE.findall(html), PLAY_RE.findall(html)
    row = {"draw_date": date, "powerball": power[0] if power else "", "power_play": play[0] if play else ""}
    for i in range(5):
        row[f"n{i + 1}"] = sorted(map(int, whites))[i] if len(whites) == 5 else ""
    return row


def fetch_official(offline: bool) -> list[dict]:
    """Every draw on powerball.com. After the first run only recent pages are fetched."""
    saved = {}
    if OFFICIAL_CSV_PATH.exists():
        with OFFICIAL_CSV_PATH.open(encoding="utf-8") as f:
            saved = {r["draw_date"]: r for r in csv.DictReader(f)}
    if offline:
        return sorted(saved.values(), key=lambda r: r["draw_date"])

    start = FIRST_DRAW
    if saved:
        start = (date.fromisoformat(max(saved)) - timedelta(days=REFETCH_DAYS)).isoformat()
    end = date.today().isoformat()
    try:
        new = 0
        for page in range(1, 1000):
            cards = fetch_page(start, end, page)
            if not cards:
                break
            for d, html in cards:
                new += d not in saved
                saved[d] = parse_card(d, html)
            time.sleep(0.5)  # be polite to the site
        rows = sorted(saved.values(), key=lambda r: r["draw_date"])
        OFFICIAL_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with OFFICIAL_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=OFFICIAL_COLUMNS)
            w.writeheader()
            w.writerows(rows)
        print(f"powerball.com: {new} new draw(s) since {start} -> {OFFICIAL_CSV_PATH.relative_to(HERE)}")
        return rows
    except Exception as exc:  # network problems etc.
        print(f"powerball.com download failed ({exc}); using saved CSV.", file=sys.stderr)
        if not saved:
            sys.exit("No data available: download failed and no saved CSV.")
        return sorted(saved.values(), key=lambda r: r["draw_date"])


def parse_draws(official: list[dict]) -> list[tuple]:
    """Official draws, with the archive filling in draws the site shows no numbers for."""
    with ARCHIVE_PATH.open(encoding="utf-8") as f:
        archive = {r["draw_date"]: r for r in csv.DictReader(f)}
    rows, missing = [], []
    for rec in official:
        d = rec["draw_date"]
        if rec["n1"] and rec["powerball"]:
            src = rec
            source = "powerball_com"
        elif d in archive:
            src, source = archive[d], "archive_1992_1997"
        else:
            missing.append(d)
            continue
        whites = sorted(int(src[f"n{i}"]) for i in range(1, 6))
        play = str(rec.get("power_play") or "")
        rows.append((d, *whites, int(src["powerball"]), int(play) if play.isdigit() else None, source))
    if missing:
        print(f"Warning: no numbers found for {len(missing)} draw(s), e.g. {missing[:3]}", file=sys.stderr)
    return rows


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
        f"({first} to {last}): "
        + ", ".join(f"{n:,} from {src}" for src, n in
                    con.execute("SELECT source, COUNT(*) FROM draws GROUP BY source ORDER BY source DESC"))
        + "._",
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
    ap.add_argument("--offline", action="store_true", help="skip download, use the saved CSVs in data/")
    args = ap.parse_args()

    draws = parse_draws(fetch_official(args.offline))
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
