# 🎱 Project 2: Mega Millions Number Generator

A number generator built on **every Mega Millions draw ever held**: 2,554+ drawings from the first one on
**May 17, 2002** to today. It loads the full history into SQLite, scores every number with SQL, and
suggests tickets for the next draw. Re-run it after each draw (or let GitHub Actions do it) to get fresh picks.

👉 **Latest picks:** [`output/latest_picks.md`](output/latest_picks.md)

## Quick start

```bash
cd project-2-mega-millions
python3 mega_millions.py              # download latest draws, write picks
python3 mega_millions.py --tickets 10 # more tickets
python3 mega_millions.py --recent 50  # shorter "hot" window
python3 mega_millions.py --offline    # use the saved CSV, no download
```

Only Python's standard library is needed (no installs).

## Data source

[NY Open Data – Lottery Mega Millions Winning Numbers: Beginning 2002](https://data.ny.gov/Government-Finance/Lottery-Mega-Millions-Winning-Numbers-Beginning-20/5xaw-6ayf).
A snapshot is saved in [`data/mega_millions_draws.csv`](data/mega_millions_draws.csv) and refreshed on every run.

## The SQL

| File | What it does |
|---|---|
| [`sql/schema.sql`](sql/schema.sql) | `eras`, `draws`, and a normalized `draw_numbers` table (one row per ball) |
| [`sql/number_stats.sql`](sql/number_stats.sql) | CTEs + window functions + a recursive CTE that score each number |
| [`sql/explore.sql`](sql/explore.sql) | Extra analysis: draws per era, top numbers, common pairs, odd/even split, sum distribution |

### The tricky part: the game changed 5 times

| Era | White balls | Mega Ball |
|---|---|---|
| May 2002 – Jun 2005 | 1–52 | 1–52 |
| Jun 2005 – Oct 2013 | 1–56 | 1–46 |
| Oct 2013 – Oct 2017 | 1–75 | 1–15 |
| Oct 2017 – Apr 2025 | 1–70 | 1–25 |
| Apr 2025 – today | 1–70 | 1–24 |

Raw counts would be misleading: white ball 60 couldn't be drawn before 2013, and Mega Ball 20 couldn't be drawn
from 2013–2017. So each number is compared only against the draws where it **was in the drum**, and against what
chance predicts for that drum size:

```
expected = Σ (balls drawn / balls in drum)   over draws where the number was eligible
lift     = actual hits / expected            (1.00 = exactly average)
```

### Score

```
score = 0.50 × all-time lift  +  0.35 × last-100-draws lift  +  0.15 × overdue ratio (capped at 2)
```

- **All-time lift**: long-run frequency across all 2,554+ draws
- **Recent lift**: "hot" numbers over the last 100 draws
- **Overdue ratio**: draws since last seen ÷ the average gap for that number

Ticket 1 is the five highest-scoring white balls + the top Mega Ball. The rest are drawn at random, weighted
toward high scores, so you get variety. The seed is the latest draw date, so picks stay the same until the next draw.

## Auto-update after every draw

[`.github/workflows/mega-millions.yml`](../.github/workflows/mega-millions.yml) runs every Wednesday and Saturday
(after the Tuesday/Friday draws), downloads the new result, and commits the updated picks. It can also be run by
hand from the **Actions** tab. (Scheduled workflows only run once this is merged into the default branch.)

## ⚠️ Reality check

Lottery draws are independent and random: every combination has the same 1 in 290,472,336 jackpot odds, and no
amount of history changes that. This project is a fun SQL/data exercise, not a winning strategy. Please play responsibly.

## Takeaways

- Normalizing data into a long table (`draw_numbers`) made frequency queries much simpler than working with `n1..n5` columns.
- Lookup tables (`eras`) joined on a date range are a clean way to handle business rules that change over time.
- A recursive CTE can generate the full list of possible numbers, so numbers that were *never* drawn still show up.
