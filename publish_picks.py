#!/usr/bin/env python3
"""Check the last picks against the newest draw and publish LATEST_PICKS.md.

Run after project-2-mega-millions/mega_millions.py and
project-3-powerball/powerball.py. Each writes:
  output/latest_picks.json    picks for the next draw (+ recent results)
  output/previous_picks.json  the picks made before the newest draw

For each game, the previous picks are checked against the first draw after
they were made. Every check is saved to output/pick_history.json, which feeds
the running totals. Matches are shown in green, misses in red.
"""
import json
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME_DIRS = [HERE / "project-2-mega-millions", HERE / "project-3-powerball"]
OUT = HERE / "LATEST_PICKS.md"

GREEN, RED = "🟢", "🔴"
# Balls in the drum today: chance that a picked white ball is drawn = 5 / WHITE_MAX.
WHITE_MAX = {"Mega Millions": 70, "Powerball": 69}


def fmt(nums):
    return " ".join(f"{n:02d}" for n in nums)


def nice(iso):
    return f"{date.fromisoformat(iso):%a %b %-d, %Y}"


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def prize(white_hits, ball_hit, ball_name):
    """Same prize structure for both games: 3+ white balls, or the ball with any whites."""
    if white_hits == 5 and ball_hit:
        return "JACKPOT"
    return "Yes" if white_hits >= 3 or ball_hit else "No"


def check(prev, result, ball_name):
    tickets = []
    for t in prev["tickets"]:
        hits = sorted(set(t["white"]) & set(result["white"]))
        ball_hit = t["ball"] == result["ball"]
        tickets.append({**t, "white_hits": hits, "ball_hit": ball_hit,
                        "prize": prize(len(hits), ball_hit, ball_name)})
    return {"draw_date": result["date"], "result": result,
            "picks_made_after": prev["latest_draw"]["date"], "tickets": tickets}


def update_history(game_dir, game):
    """Check the previous picks against the next draw, once per draw."""
    out = game_dir / "output"
    history_path = out / "pick_history.json"
    history = load(history_path) or []
    prev = load(out / "previous_picks.json")
    if prev:
        made_after = prev["latest_draw"]["date"]
        upcoming = [d for d in game["recent_draws"] if d["date"] > made_after]
        if upcoming and upcoming[0]["date"] not in {h["draw_date"] for h in history}:
            history.append(check(prev, upcoming[0], game["ball_name"]))
            history.sort(key=lambda h: h["draw_date"])
            history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    return history


def ticket_row(i, t, ball_name):
    whites = " ".join(f"{GREEN}**{n:02d}**" if n in t["white_hits"] else f"{RED}{n:02d}" for n in t["white"])
    ball = f"{GREEN}**{t['ball']:02d}**" if t["ball_hit"] else f"{RED}{t['ball']:02d}"
    matches = len(t["white_hits"])
    if matches and t["ball_hit"]:
        label = f"{matches} white + {ball_name}"
    elif t["ball_hit"]:
        label = f"{ball_name} only"
    else:
        label = f"{matches} white" if matches else "0"
    return f"| {i} | {whites} | {ball} | {label} | {t['prize']} |"


def render_check(game, history):
    name, ball = game["game"], game["ball_name"]
    if not history:
        return [f"### How the last picks did", "",
                "_No draw has happened since these picks were first made. Check back after the next draw._", ""]
    last = history[-1]
    r = last["result"]
    lines = [
        f"### How the last picks did: {nice(last['draw_date'])}",
        "",
        f"Result: **{fmt(r['white'])}**, {ball} **{r['ball']:02d}**  ",
        f"{GREEN} = matched, {RED} = didn't match",
        "",
        f"| # | White balls | {ball} | Matches | Prize |",
        "|---:|---|---|---|---|",
    ]
    lines += [ticket_row(i, t, ball) for i, t in enumerate(last["tickets"], 1)]

    tickets = [t for h in history for t in h["tickets"]]
    white_hits = sum(len(t["white_hits"]) for t in tickets)
    ball_hits = sum(t["ball_hit"] for t in tickets)
    prizes = sum(t["prize"] != "No" for t in tickets)
    chance = 5 * 5 / WHITE_MAX[name]
    lines += [
        "",
        f"**Running total** ({len(history)} draw{'s' if len(history) != 1 else ''}, {len(tickets)} tickets): "
        f"{white_hits} white-ball match{'es' if white_hits != 1 else ''} "
        f"({white_hits / len(tickets):.2f} per ticket; pure chance is {chance:.2f}), "
        f"{ball_hits} {ball} match{'es' if ball_hits != 1 else ''}, "
        f"{prizes} prize{'s' if prizes != 1 else ''}.",
        "",
    ]
    return lines


def main():
    lines = [
        "# 🎱 Latest lottery picks",
        "",
        "Updated automatically about an hour after every Mega Millions and Powerball draw, using results pulled",
        "directly from [megamillions.com](https://www.megamillions.com/) and [powerball.com](https://www.powerball.com/).",
        "",
    ]
    for game_dir in GAME_DIRS:
        game = load(game_dir / "output" / "latest_picks.json")
        history = update_history(game_dir, game)
        nxt = game["next_draw"]
        lines += [f"## {game['game']}", ""]
        lines += render_check(game, history)
        lines += [
            f"### Picks for the next draw: {nice(nxt['date'])} at {nxt['time']}",
            "",
            f"Based on {game['draws_used']:,} draws since {nice(game['first_draw'])}.",
            "",
            f"| # | White balls | {game['ball_name']} |",
            "|---:|---|---:|",
        ]
        lines += [f"| {i} | **{fmt(t['white'])}** | **{t['ball']:02d}** |" for i, t in enumerate(game["tickets"], 1)]
        lines += ["", f"Full report: [{game_dir.name}/output/latest_picks.md]({game_dir.name}/output/latest_picks.md)", ""]
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
