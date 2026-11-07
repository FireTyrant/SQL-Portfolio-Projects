# 🔴 Project 3: Powerball Number Generator

A number generator built on **every Powerball draw ever held**: 3,877+ drawings from the very first one on
**April 22, 1992** to today. It loads the full history into SQLite, scores every number with SQL, and suggests
tickets for the next draw. It refreshes automatically after every Monday, Wednesday and Saturday draw.

👉 **Latest picks:** [`output/latest_picks.md`](output/latest_picks.md)

## Quick start

```bash
cd project-3-powerball
python3 powerball.py              # download latest draws, write picks
python3 powerball.py --tickets 10 # more tickets
python3 powerball.py --recent 50  # shorter "hot" window
python3 powerball.py --offline    # use the saved CSVs, no download
```

Only Python's standard library is needed (no installs).

## Data sources

| Draws | Source | File |
|---|---|---|
| Nov 1, 1997 → today | [powerball.com](https://www.powerball.com/previous-results?gc=powerball), the official site | [`data/powerball_official.csv`](data/powerball_official.csv) |
| Apr 22, 1992 → Oct 29, 1997 | [powerball.net archive](https://www.powerball.net/archive/1992) (powerball.com lists these 577 draws but shows no numbers for them) | [`data/powerball_draws_1992_2010.csv`](data/powerball_draws_1992_2010.csv) |

The first run downloads every page of powerball.com's history (about 2 minutes). Later runs re-download only the last
30 days, so they take about a second. How the sources were checked:

- powerball.com lists all 3,877 draw dates, and the archive's dates match them exactly.
- For the 1,279 draws from 1997 to 2010 that both have, the archive matches powerball.com **exactly**, so it can be
  trusted for the 1992–1997 draws the official site leaves blank.
- powerball.com also matched all 2,021 draws in NY Open Data, the source used before.

Every draw is also checked against its era's number ranges every time the script runs. The `draws.source` column
records where each row came from.

## The SQL

| File | What it does |
|---|---|
| [`sql/schema.sql`](sql/schema.sql) | `eras`, `draws` (with a `source` column), and a normalized `draw_numbers` table |
| [`sql/number_stats.sql`](sql/number_stats.sql) | CTEs + window functions + a recursive CTE that score each number |
| [`sql/explore.sql`](sql/explore.sql) | Draws per era, top numbers, common pairs, odd/even split, sum distribution, top Powerballs |

### The game changed 7 times

| Era | White balls | Powerball | Draws |
|---|---|---|---:|
| Apr 1992 – Nov 1997 | 1–45 | 1–45 | 578 |
| Nov 1997 – Oct 2002 | 1–49 | 1–42 | 514 |
| Oct 2002 – Aug 2005 | 1–53 | 1–42 | 302 |
| Aug 2005 – Jan 2009 | 1–55 | 1–42 | 350 |
| Jan 2009 – Jan 2012 | 1–59 | 1–39 | 316 |
| Jan 2012 – Oct 2015 | 1–59 | 1–35 | 388 |
| Oct 2015 – today | 1–69 | 1–26 | 1,429+ |

Raw counts would be misleading: white balls 60–69 have only existed since 2015, so they've had far fewer chances.
Each number is compared only against draws where it **was in the drum**, and against what chance predicts for
that drum size:

```
expected = Σ (balls drawn / balls in drum)   over draws where the number was eligible
lift     = actual hits / expected            (1.00 = exactly average)
score    = 0.50 × all-time lift + 0.35 × last-100-draws lift + 0.15 × overdue ratio (capped at 2)
```

Ticket 1 is the five highest-scoring white balls + the top Powerball. The rest are drawn at random, weighted toward
high scores. The seed is the latest draw date, so picks stay the same until the next draw.

## 🌴 Playing in California

The numbers drawn are the same in every state, so the picks don't change. Two things are different in California:

- **No Power Play.** California doesn't sell it, so ignore the `power_play` column.
- **Prizes are pari-mutuel.** California sets every prize below the jackpot by how many people won it, so if lots of
  people pick the same numbers, a prize gets split more ways. Many players choose birthdays (1–31). Numbers
  **above 31** don't change your odds of winning, but they may mean sharing less if you do.

## Auto-update after every draw

[`.github/workflows/lottery-picks.yml`](../.github/workflows/lottery-picks.yml) runs about **1 hour after every
Mega Millions and Powerball draw**. Each run pulls new results straight from megamillions.com and powerball.com,
updates the picks for **both** games, and publishes 5 tickets for each in [`LATEST_PICKS.md`](../LATEST_PICKS.md).
Each update also checks the previous picks against the new result, with matches in 🟢 green and misses in 🔴
red, and keeps a running total in `output/pick_history.json`. A run that finds no new draw saves nothing. It can also be run by hand from the **Actions** tab.

## ⚠️ Reality check

Lottery draws are independent and random: every combination has the same 1 in 292,201,338 jackpot odds, and no
amount of history changes that. This project is a fun SQL/data exercise, not a winning strategy. Please play responsibly.

## Takeaways

- Combining an official source with an unofficial one is fine **if you validate the overlap** and record where each
  row came from (`source` column).
- A data-quality check written in SQL (draws that break their era's rules) is a cheap guard against bad input.
