#!/usr/bin/env python3
"""Mega Millions number generator built on every published draw.

Steps:
  1. Download the draw history from two sources and combine them:
       - megamillions.com (official): Feb 2010 -> latest draw, posted within
         minutes of each drawing
       - NY State open data: May 2002 -> latest, used for 2002-2010
     Where both have a draw, the official site wins (NY has 2 known errors,
     confirmed against the Texas Lottery). Saved CSVs in data/ are used if a
     download fails.
  2. Load it into a SQLite database (output/mega_millions.db) using the
     schema in sql/schema.sql.
  3. Score every number in the current game with sql/number_stats.sql:
        - all-time lift   : hits vs. what chance predicts (era-adjusted)
        - recent lift     : same, over the last N draws ("hot" numbers)
        - overdue ratio   : draws since last hit vs. the average gap
  4. Write the picks for the next draw to output/latest_picks.md.

Run it again after every draw (Tuesday & Friday) to refresh the picks.

Standard library only:  python3 mega_millions.py [--tickets 5] [--recent 100]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_URL = "https://data.ny.gov/api/views/5xaw-6ayf/rows.csv?accessType=DOWNLOAD"
OFFICIAL_URL = "https://www.megamillions.com/cmspages/utilservice.asmx/GetDrawingPagingData"
OFFICIAL_PAGE_SIZE = 100  # the site rejects larger pages

HERE = Path(__file__).resolve().parent
SQL_DIR = HERE / "sql"
CSV_PATH = HERE / "data" / "mega_millions_draws.csv"
OFFICIAL_CSV_PATH = HERE / "data" / "mega_millions_official.csv"
OFFICIAL_COLUMNS = ["draw_date", "n1", "n2", "n3", "n4", "n5", "mega_ball", "megaplier"]
OUT_DIR = HERE / "output"
DB_PATH = OUT_DIR / "mega_millions.db"
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
            req = urllib.request.Request(DATA_URL, headers={"User-Agent": "mega-millions-generator"})
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


def fetch_official(offline: bool) -> list[dict]:
    """All draws on megamillions.com (Feb 2010 onward), one page at a time."""
    if not offline:
        try:
            rows, page, total = [], 1, None
            while total is None or len(rows) < total:
                body = json.dumps({"pageNumber": page, "pageSize": OFFICIAL_PAGE_SIZE,
                                   "startDate": "", "endDate": ""}).encode()
                req = urllib.request.Request(OFFICIAL_URL, data=body, headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "mega-millions-generator"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(json.loads(resp.read().decode("utf-8"))["d"])
                total = data["TotalResults"]
                if not data["DrawingData"]:
                    break
                for r in data["DrawingData"]:
                    rows.append({
                        "draw_date": r["PlayDate"][:10],
                        **{f"n{i}": r[f"N{i}"] for i in range(1, 6)},
                        "mega_ball": r["MBall"],
                        "megaplier": r["Megaplier"] if r["Megaplier"] and r["Megaplier"] > 0 else "",
                    })
                page += 1
            if len(rows) < total:
                raise ValueError(f"got {len(rows)} of {total} draws")
            rows.sort(key=lambda r: r["draw_date"])
            with OFFICIAL_CSV_PATH.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=OFFICIAL_COLUMNS)
                w.writeheader()
                w.writerows(rows)
            print(f"Downloaded {len(rows):,} official draws -> {OFFICIAL_CSV_PATH.relative_to(HERE)}")
            return rows
        except Exception as exc:
            print(f"Official download failed ({exc}); using saved CSV.", file=sys.stderr)
    if not OFFICIAL_CSV_PATH.exists():
        print("No official data saved; using NY data only.", file=sys.stderr)
        return []
    with OFFICIAL_CSV_PATH.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_draws(text: str, official: list[dict]) -> list[tuple]:
    """Combine NY open data with the official site; official wins on overlap."""
    rows = {}
    for rec in csv.DictReader(io.StringIO(text)):
        date = datetime.strptime(rec["Draw Date"].strip(), "%m/%d/%Y").date().isoformat()
        whites = sorted(int(x) for x in rec["Winning Numbers"].split())
        if len(whites) != 5 or len(set(whites)) != 5:
            print(f"Skipping malformed draw {date}: {rec['Winning Numbers']}", file=sys.stderr)
            continue
        mega = int(rec["Mega Ball"])
        mult = (rec.get("Multiplier") or "").strip()
        rows[date] = (date, *whites, mega, int(mult) if mult.isdigit() else None, "ny_open_data")

    for rec in official:
        whites = sorted(int(rec[f"n{i}"]) for i in range(1, 6))
        mult = str(rec["megaplier"]).strip()
        rows[rec["draw_date"]] = (rec["draw_date"], *whites, int(rec["mega_ball"]),
                                  int(mult) if mult.isdigit() else None, "megamillions_com")
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
        [(d[0], "white", n) for d in draws for n in d[1:6]] + [(d[0], "mega", d[6]) for d in draws],
    )
    con.commit()
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


def make_tickets(whites, megas, count, rng) -> list[tuple[str, list[int], int]]:
    tickets = [("Top scores", sorted(s["number"] for s in whites[:5]), megas[0]["number"])]
    seen = {tuple(tickets[0][1]) + (tickets[0][2],)}
    while len(tickets) < count:
        w = weighted_sample(whites, 5, rng)
        m = weighted_sample(megas, 1, rng)[0]
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


def write_report(con, whites, megas, tickets, recent) -> str:
    total, first, last = con.execute("SELECT COUNT(*), MIN(draw_date), MAX(draw_date) FROM draws").fetchone()
    latest = con.execute("SELECT * FROM draws ORDER BY draw_date DESC LIMIT 1").fetchone()
    cold = sorted(whites, key=lambda s: (s["score"], s["number"]))[:10]

    lines = [
        "# Mega Millions picks for the next draw",
        "",
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from **{total:,} draws** "
        f"({first} to {last}): "
        + ", ".join(f"{n:,} from {src}" for src, n in
                    con.execute("SELECT source, COUNT(*) FROM draws GROUP BY source ORDER BY source DESC"))
        + "._",
        "",
        f"**Latest draw ({latest[0]}):** {fmt(latest[1:6])}  Mega Ball **{latest[6]:02d}**",
        "",
        "## Tickets",
        "",
        "| # | Method | White balls | Mega Ball |",
        "|---:|---|---|---:|",
    ]
    for i, (method, w, m) in enumerate(tickets, 1):
        lines.append(f"| {i} | {method} | **{fmt(w)}** | **{m:02d}** |")
    lines += [
        "",
        "## Top white balls (1-70)",
        "",
        *stats_table(whites, 15, recent),
        "",
        "## Top Mega Balls (1-24)",
        "",
        *stats_table(megas, 8, recent),
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
        "**Reality check:** every Mega Millions draw is independent and every number is equally likely. "
        "These picks reflect past patterns only; they do not change your odds "
        "(1 in 290,472,336 for the jackpot). Play for fun.",
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
    ap.add_argument("--offline", action="store_true", help="skip downloads, use the saved CSVs in data/")
    args = ap.parse_args()

    draws = parse_draws(fetch_csv(args.offline), fetch_official(args.offline))
    con = build_db(draws)
    whites = number_stats(con, "white", args.recent)
    megas = number_stats(con, "mega", args.recent)

    seed = args.seed if args.seed is not None else int(draws[-1][0].replace("-", ""))
    tickets = make_tickets(whites, megas, max(1, args.tickets), random.Random(seed))
    write_report(con, whites, megas, tickets, args.recent)

    print(f"\nLoaded {len(draws):,} draws ({draws[0][0]} to {draws[-1][0]}).")
    print("Picks for the next draw:")
    for i, (method, w, m) in enumerate(tickets, 1):
        print(f"  {i}. {fmt(w)}  Mega Ball {m:02d}   ({method})")
    print(f"\nFull report: {PICKS_PATH.relative_to(HERE)}")


if __name__ == "__main__":
    main()
