"""
Ticketmaster listing prep (Option A — assisted manual listing).

Ticketmaster has no public API that lets an individual list tickets for
resale; listing is a manual action inside the TM account/app. So instead of
calling an API, when a game is skipped we *prep* the decision — which games,
and a suggested price per seat pair — and send the owner a link to finish the
listing in Ticketmaster. The owner then confirms back with `listed <days>`.

This module owns the pricing suggestion and the prep-message formatting.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from app.config import settings


def suggested_price(pair_index: int, day_of_week: str) -> float:
    """Suggested Ticketmaster list price for one seat pair on a given day."""
    pair = settings.seat_pairs[pair_index]
    price = pair.list_price
    if day_of_week in ("Friday", "Saturday"):
        price += settings.weekend_premium
    return price


def game_avg_price(day_of_week: str) -> float:
    """Average suggested price across both seat pairs (stored as listed_price)."""
    prices = [suggested_price(i, day_of_week) for i in range(len(settings.seat_pairs))]
    return sum(prices) / len(prices)


def _short(g: sqlite3.Row) -> str:
    d = date.fromisoformat(g["date"])
    return f"{g['day_of_week'][:3]} {d.month}/{d.day}"


def build_prep_message(skip_games: list[sqlite3.Row]) -> str:
    """
    Build the 'ready to list on Ticketmaster' message for skipped games.

    Returns an empty string if there are no skip games (caller can append
    unconditionally).
    """
    if not skip_games:
        return ""

    lines = ["", "🏷️ **Ready to list on Ticketmaster:**", ""]
    for g in skip_games:
        lines.append(f"  **{_short(g)}** vs {g['opponent']}")
        for i, pair in enumerate(settings.seat_pairs):
            price = suggested_price(i, g["day_of_week"])
            lines.append(f"    • Pair {i + 1} (Sec {pair.section}/Row {pair.row}): ${price:.0f}")
    lines.append("")
    lines.append(f"List them here → {settings.ticketmaster_sell_url}")
    lines.append("Then reply `listed all` (or `listed Tue, Thu`) once they're up.")
    return "\n".join(lines)
