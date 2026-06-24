#!/usr/bin/env python3
"""
Sell-link test helper.

Shows, for upcoming games, exactly which Ticketmaster URL the bot's prep
message will hand you — a real per-game link if one is saved, otherwise the
generic account page. Use it to (a) see what's saved and (b) eyeball/click the
links before trusting them in the weekly prompt.

Run from the repo root:
    .venv/bin/python -m scripts.check_sell_links            # next 10 games
    .venv/bin/python -m scripts.check_sell_links 20         # next 20 games
"""
from __future__ import annotations

import sys
from datetime import date

from app.database import create_tables, get_next_games
from app.listing.prep import sell_url


def main() -> None:
    create_tables()  # applies the tm_sell_url migration if needed
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    games = get_next_games(limit=limit)
    if not games:
        print("No upcoming games.")
        return

    specific = 0
    print(f"\nSell links for the next {len(games)} game(s):\n")
    for g in games:
        d = date.fromisoformat(g["date"])
        url, is_specific = sell_url(g)
        tag = "✅ saved link" if is_specific else "⬜ generic page"
        if is_specific:
            specific += 1
        print(f"  {g['day_of_week'][:3]} {d.month}/{d.day}  vs {g['opponent']}")
        print(f"      [{tag}] {url}")
    print(f"\n{specific}/{len(games)} games have a saved Ticketmaster event id.")
    print("Save one with the Discord command:  link 6/30 1459  (id or full URL)\n")


if __name__ == "__main__":
    main()
