"""
Parse the owner's reply to the weekly prompt and update game statuses.

Supported commands (case-insensitive, flexible punctuation):
  skip all                 → mark all next-week upcoming games as 'skip'
  attending all            → mark all next-week upcoming games as 'attending'
  skip tue, thu            → mark Tue & Thu games as 'skip', rest as 'attending'
  listed all               → mark skipped games as 'listed' (you finished on TM)
  listed tue, 4/2          → mark specific skipped games as 'listed'
  sold all / sold tue      → mark listed games as 'sold' (feeds P&L)
  status                   → show current week's game statuses
  help                     → show command reference

Day matching is fuzzy: "tue", "tues", "tuesday" all work. Confirm commands
(`listed`/`sold`) also accept dates like "4/2".

Ticketmaster has no public API to auto-list, so skipping a game does NOT list
it automatically. Instead the bot replies with a prep message (suggested price
per seat pair + a link to finish on TM); you then confirm with `listed`.
"""

import logging
import re
import sqlite3
from datetime import date

import discord

from app.database import (
    get_games_by_status,
    get_games_for_week,
    get_next_games,
    log_activity,
    mark_listed,
    mark_sold,
    next_week_bounds,
    set_game_tm_url,
    update_game_status,
)
from app.listing.prep import build_prep_message, game_avg_price

log = logging.getLogger(__name__)

# Map common abbreviations → canonical day name (title-case)
DAY_ALIASES: dict[str, str] = {
    "mon": "Monday", "monday": "Monday",
    "tue": "Tuesday", "tues": "Tuesday", "tuesday": "Tuesday",
    "wed": "Wednesday", "weds": "Wednesday", "wednesday": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "thursday": "Thursday",
    "fri": "Friday", "friday": "Friday",
    "sat": "Saturday", "saturday": "Saturday",
    "sun": "Sunday", "sunday": "Sunday",
}


def _parse_days(text: str) -> list[str]:
    """Extract canonical day names from freeform text."""
    found = []
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in DAY_ALIASES:
            day = DAY_ALIASES[w]
            if day not in found:
                found.append(day)
    return found


def _parse_dates(text: str) -> list[tuple[int, int]]:
    """Extract (month, day) pairs from text like '4/2'."""
    return [(int(m), int(d)) for m, d in re.findall(r"\b(\d{1,2})/(\d{1,2})\b", text)]


def _select(candidates: list[sqlite3.Row], text: str) -> list[sqlite3.Row]:
    """Pick games referenced in `text` — 'all', day names, or m/d dates."""
    if re.search(r"\ball\b", text):
        return list(candidates)
    days = set(_parse_days(text))
    dates = set(_parse_dates(text))
    out = []
    for g in candidates:
        d = date.fromisoformat(g["date"])
        if g["day_of_week"] in days or (d.month, d.day) in dates:
            out.append(g)
    return out


def _status_emoji(status: str) -> str:
    return {
        "attending": "✅",
        "skip": "🟡",      # decided to sell, not yet listed
        "listed": "🏷️",
        "sold": "💰",
        "upcoming": "⬜",
    }.get(status, "❓")


def _short(g: sqlite3.Row) -> str:
    d = date.fromisoformat(g["date"])
    return f"{g['day_of_week'][:3]} {d.month}/{d.day}"


def _status_label(g: sqlite3.Row) -> str:
    s = g["status"]
    if s == "skip":
        return "TO LIST"
    if s == "listed":
        return f"LISTED (${g['listed_price']:.0f}/pair)" if g["listed_price"] else "LISTED"
    if s == "sold":
        return f"SOLD (${g['sold_price']:.0f})" if g["sold_price"] else "SOLD"
    return s.upper()


def _build_confirmation(games: list[sqlite3.Row]) -> str:
    lines = ["Got it! Here's your week:\n"]
    for g in games:
        lines.append(f"  {_status_emoji(g['status'])} {_short(g)}  vs {g['opponent']} — {_status_label(g)}")
    lines.append("\nReply `skip <days>` to adjust, or `status` to check again.")
    return "\n".join(lines)


def _build_status_message(games: list[sqlite3.Row]) -> str:
    if not games:
        return "No upcoming games found."
    first_date = date.fromisoformat(games[0]["date"])
    last_date = date.fromisoformat(games[-1]["date"])
    header = f"📋 **Upcoming games ({first_date.strftime('%b %d')} – {last_date.strftime('%b %d')}):**\n"
    lines = [header]
    for g in games:
        lines.append(f"  {_status_emoji(g['status'])} {_short(g)}  vs {g['opponent']} — {_status_label(g)}")
    return "\n".join(lines)


def _confirm_summary(verb: str, games: list[sqlite3.Row]) -> str:
    lines = [f"✅ {verb} {len(games)} game(s):"]
    for g in games:
        lines.append(f"  • {_short(g)} vs {g['opponent']}")
    return "\n".join(lines)


def _skip_reply(games: list[sqlite3.Row]) -> str:
    """Confirmation for the week + the Ticketmaster listing prep for skipped games."""
    reply = _build_confirmation(games)
    skip_games = [g for g in games if g["status"] == "skip"]
    prep = build_prep_message(skip_games)
    return reply + ("\n" + prep if prep else "")


HELP_TEXT = """
🐂 **Bulls Ticket Manager — Commands**

`skip all`          → mark all games next week to sell
`attending all`     → keep all games next week
`skip Tue, Thu`     → sell specific days (rest = attending)
`listed all`        → confirm you listed them on Ticketmaster
`listed Tue, 4/2`   → confirm specific games are listed
`sold Tue`          → mark a game's tickets sold (feeds P&L)
`link 4/2 <url>`    → save the TM sell link for that game
`status`            → show next week's current decisions
`help`              → show this message

Skipping a game doesn't auto-list (Ticketmaster has no API for that) — I'll
send you the price + a link, you finish in the TM app, then reply `listed`.
""".strip()


async def handle_reply(message: discord.Message) -> None:
    raw = message.content.strip()
    text = raw.lower()
    monday, sunday = next_week_bounds()
    games = get_games_for_week(monday, sunday)

    # --- help ---
    if text in ("help", "?"):
        await message.channel.send(HELP_TEXT)
        return

    # --- status ---
    if text == "status":
        upcoming = get_next_games(limit=7)
        await message.channel.send(_build_status_message(upcoming))
        return

    # --- link <date> <url> --- save the Ticketmaster sell link for one game
    if text.startswith("link"):
        m = re.search(r"https?://\S+", raw)  # use raw — keep URL case intact
        if not m:
            await message.channel.send("To save a sell link: `link 4/2 https://...`")
            return
        url = m.group(0)
        selector = raw[: m.start()]  # text before the url (excludes the url's own digits)
        dates = set(_parse_dates(selector))
        if not dates:
            await message.channel.send("Use a date so I know which game: `link 4/2 https://...`")
            return
        candidates = get_next_games(limit=400)  # whole rest of the season
        targets = [
            g for g in candidates
            if (date.fromisoformat(g["date"]).month, date.fromisoformat(g["date"]).day) in dates
        ]
        if not targets:
            await message.channel.send("No upcoming game matches that date. Check `status`.")
            return
        for g in targets:
            set_game_tm_url(g["id"], url)
            log_activity(g["id"], "tm_url_set", {"url": url})
        await message.channel.send(_confirm_summary("Saved sell link for", targets))
        return

    # --- sold <days/dates/all> ---  (check before 'listed'/'skip')
    if re.search(r"\bsold\b", text):
        candidates = get_games_by_status(("listed",))
        targets = _select(candidates, text)
        if not targets:
            await message.channel.send(
                "Nothing to mark sold. Mark games `listed` first, or check `status`."
            )
            return
        for g in targets:
            price = g["listed_price"] if g["listed_price"] else game_avg_price(g["day_of_week"])
            mark_sold(g["id"], price)
            log_activity(g["id"], "sold", {"source": "discord_reply", "price": price})
        await message.channel.send(_confirm_summary("Sold", targets))
        return

    # --- listed <days/dates/all> ---
    if re.search(r"\blisted?\b", text):
        candidates = get_games_by_status(("skip",))
        targets = _select(candidates, text)
        if not targets:
            await message.channel.send(
                "Nothing to mark listed. Reply `skip <days>` first, or check `status`."
            )
            return
        for g in targets:
            mark_listed(g["id"], game_avg_price(g["day_of_week"]))
            log_activity(g["id"], "listed", {"source": "discord_reply"})
        await message.channel.send(_confirm_summary("Listed", targets))
        return

    # --- attending all ---
    if re.search(r"\battending\s+all\b", text):
        if not games:
            await message.channel.send("No games found for next week.")
            return
        for g in games:
            if g["status"] == "upcoming":
                update_game_status(g["id"], "attending")
                log_activity(g["id"], "attending", {"source": "discord_reply"})
        games = get_games_for_week(monday, sunday)
        await message.channel.send(_build_confirmation(games))
        return

    # --- skip all ---
    if re.search(r"\bskip\s+all\b", text):
        if not games:
            await message.channel.send("No games found for next week.")
            return
        for g in games:
            if g["status"] == "upcoming":
                update_game_status(g["id"], "skip")
                log_activity(g["id"], "skipped", {"source": "discord_reply"})
        games = get_games_for_week(monday, sunday)
        await message.channel.send(_skip_reply(games))
        return

    # --- skip <specific days> ---
    if re.search(r"\bskip\b", text):
        skip_days = _parse_days(text)
        if not skip_days:
            await message.channel.send(
                "I couldn't parse any days from that. Try: `skip Tue, Thu` or `skip all`."
            )
            return
        if not games:
            await message.channel.send("No games found for next week.")
            return

        for g in games:
            if g["status"] not in ("upcoming", "attending", "skip"):
                continue  # don't touch listed/sold games
            if g["day_of_week"] in skip_days:
                update_game_status(g["id"], "skip")
                log_activity(g["id"], "skipped", {"source": "discord_reply", "matched_day": g["day_of_week"]})
            else:
                update_game_status(g["id"], "attending")
                log_activity(g["id"], "attending", {"source": "discord_reply"})

        games = get_games_for_week(monday, sunday)
        await message.channel.send(_skip_reply(games))
        return

    # --- unrecognized ---
    await message.channel.send(
        "I didn't understand that. Reply `help` for a list of commands."
    )
