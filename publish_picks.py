#!/usr/bin/env python3
"""Combine the latest Mega Millions and Powerball picks into LATEST_PICKS.md.

Run after project-2-mega-millions/mega_millions.py and
project-3-powerball/powerball.py, which each write output/latest_picks.json.
"""
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAMES = [
    HERE / "project-2-mega-millions" / "output" / "latest_picks.json",
    HERE / "project-3-powerball" / "output" / "latest_picks.json",
]
OUT = HERE / "LATEST_PICKS.md"


def fmt(nums):
    return " ".join(f"{n:02d}" for n in nums)


def nice(iso):
    return f"{date.fromisoformat(iso):%a %b %-d, %Y}"


def main():
    lines = [
        "# 🎱 Latest lottery picks",
        "",
        "Updated automatically about an hour after every Mega Millions and Powerball draw, using results pulled",
        "directly from [megamillions.com](https://www.megamillions.com/) and [powerball.com](https://www.powerball.com/).",
        "",
    ]
    for path in GAMES:
        g = json.loads(path.read_text(encoding="utf-8"))
        latest, nxt = g["latest_draw"], g["next_draw"]
        lines += [
            f"## {g['game']}: next draw {nice(nxt['date'])} at {nxt['time']}",
            "",
            f"Latest result ({nice(latest['date'])}): **{fmt(latest['white'])}**, {g['ball_name']} **{latest['ball']:02d}**  ",
            f"Based on {g['draws_used']:,} draws since {nice(g['first_draw'])}.",
            "",
            f"| # | White balls | {g['ball_name']} |",
            "|---:|---|---:|",
        ]
        for i, t in enumerate(g["tickets"], 1):
            lines.append(f"| {i} | **{fmt(t['white'])}** | **{t['ball']:02d}** |")
        lines += ["", f"Full report: [{path.parent.parent.name}/output/latest_picks.md]"
                      f"({path.parent.parent.name}/output/latest_picks.md)", ""]
    lines += [
        "---",
        "",
        "Ticket 1 in each game uses the top-scoring numbers; tickets 2-5 are weighted-random picks. Every combination",
        "has the same odds of winning: past draws don't predict future ones. Play for fun.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT.name}")


if __name__ == "__main__":
    main()
