"""
Parse the owner's reply to the weekly prompt and update game statuses.

The weekly decision is two-step now:
  1. Attend or not:   `attending all` / `skip Tue, Thu` / `skip all`
  2. For each skipped game the bot asks **list or transfer?**, and you answer:
        `list Thu`         → list that game for resale (price + link prep)
        `transfer Fri`     → transfer that game to someone (link prep, no price)
        `list all` / `transfer all`
        `list Thu, transfer Fri`   (one message, mixed)

Then confirm once you've done it on Ticketmaster:
        `listed Thu`       → it's live on the resale market
        `sold Thu`         → it sold (feeds P&L)
        `transferred Fri`  → you sent it

Other commands: `link 6/30 1459` (save a game's TM link), `status`, `help`.

Day matching is fuzzy ("tue"/"tues"/"tuesday"). `listed`/`sold`/`transferred`
also accept m/d dates like "7/2". Ticketmaster has no public listing API, so the
bot never lists/transfers for you — it preps the decision + a link, you finish in
the TM app, then confirm.

Status flow:
  upcoming → attending
  upcoming → skip (decide) → to_list → listed → sold
                           → to_transfer → transferred
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
    mark_transferred,
    next_week_bounds,
    set_game_tm_event_id,
    update_game_status,
)
from app.listing.prep import build_prep_message, build_transfer_message, game_avg_price

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

# Words that set the action while scanning a disposition reply
_LIST_WORDS = {"list", "listing", "resell", "sell"}
_TRANSFER_WORDS = {"transfer", "transferring", "send", "give", "gift"}


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
    """Extract (month, day) pairs from text like '7/2'."""
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


def _parse_dispositions(text: str) -> list[tuple[str, str]]:
    """
    Scan a list/transfer reply into (action, target) pairs, where action is
    'to_list' or 'to_transfer' and target is a canonical day name or 'ALL'.

    A verb word sets the current action; day/all words after it attach to it.
    Handles `list thu, transfer fri`, `list all`, `transfer thu and fri`, etc.
    """
    assigns: list[tuple[str, str]] = []
    current: str | None = None
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in _LIST_WORDS:
            current = "to_list"
        elif w in _TRANSFER_WORDS:
            current = "to_transfer"
        elif current and w == "all":
            assigns.append((current, "ALL"))
        elif current and w in DAY_ALIASES:
            assigns.append((current, DAY_ALIASES[w]))
    return assigns


def _status_emoji(status: str) -> str:
    return {
        "upcoming": "⬜",
        "attending": "✅",
        "skip": "🟡",          # decided not to attend — awaiting list/transfer
        "to_list": "🏷️",
        "listed": "📤",
        "sold": "💰",
        "to_transfer": "🔄",
        "transferred": "🤝",
    }.get(status, "❓")


def _short(g: sqlite3.Row) -> str:
    d = date.fromisoformat(g["date"])
    return f"{g['day_of_week'][:3]} {d.month}/{d.day}"


def _status_label(g: sqlite3.Row) -> str:
    s = g["status"]
    if s == "skip":
        return "DECIDE: list or transfer?"
    if s == "to_list":
        return "TO LIST"
    if s == "listed":
        return f"LISTED (${g['listed_price']:.0f}/pair)" if g["listed_price"] else "LISTED"
    if s == "sold":
        return f"SOLD (${g['sold_price']:.0f})" if g["sold_price"] else "SOLD"
    if s == "to_transfer":
        return "TO TRANSFER"
    if s == "transferred":
        return "TRANSFERRED"
    return s.upper()


def _build_confirmation(games: list[sqlite3.Row]) -> str:
    lines = ["Got it! Here's your week:\n"]
    for g in games:
        lines.append(f"  {_status_emoji(g['status'])} {_short(g)}  vs {g['opponent']} — {_status_label(g)}")
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


def _ask_disposition(week_games: list[sqlite3.Row]) -> str:
    """Week confirmation + the list-or-transfer question for pending (skip) games."""
    reply = _build_confirmation(week_games)
    pending = [g for g in week_games if g["status"] == "skip"]
    if pending:
        reply += "\n\n🤔 For each, reply **list** or **transfer**:\n"
        for g in pending:
            reply += f"  🟡 {_short(g)} vs {g['opponent']}\n"
        reply += "e.g. `list thu, transfer fri`  ·  `list all`  ·  `transfer all`"
    return reply


HELP_TEXT = """
🐂 **Bulls Ticket Manager — Commands**

__Weekly decision__
`attending all`     → keep every game next week
`skip Tue, Thu`     → not attending those (I'll ask: list or transfer?)
`skip all`          → not attending any next week

__When I ask "list or transfer?"__
`list Thu`          → list that game for resale (I send price + link)
`transfer Fri`      → transfer that game (I send the link)
`list all` / `transfer all` · `list thu, transfer fri`

__Confirm after you do it on Ticketmaster__
`listed Thu`        → it's live for resale
`sold Thu`          → it sold (feeds P&L)
`transferred Fri`   → you sent it

__Other__
`link 6/30 1459`    → save a game's Ticketmaster link
`status` · `help`
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

    # --- link <date> <event-id-or-url> --- save a game's Ticketmaster event id
    if text.startswith("link"):
        body = raw[len("link"):].strip()
        tokens = body.split()
        if len(tokens) < 2:
            await message.channel.send(
                "Save a game's Ticketmaster link: `link 6/30 1459` "
                "(the number from .../my-events/1459), or paste the full link."
            )
            return
        value = tokens[-1]                 # last token: bare id or a full URL
        selector = " ".join(tokens[:-1])   # the rest holds the date
        dates = set(_parse_dates(selector))
        if not dates:
            await message.channel.send("Use a date so I know which game: `link 6/30 1459`")
            return
        if re.fullmatch(r"\d+", value):
            event_id = value
        else:
            idm = re.search(r"/(\d+)(?:[/?#]|$)", value)
            event_id = idm.group(1) if idm else None
        if not event_id:
            await message.channel.send(
                "I couldn't find an event id in that. Send the number "
                "(`link 6/30 1459`) or the `.../my-events/1459` link."
            )
            return
        candidates = get_next_games(limit=400)
        targets = [
            g for g in candidates
            if (date.fromisoformat(g["date"]).month, date.fromisoformat(g["date"]).day) in dates
        ]
        if not targets:
            await message.channel.send("No upcoming game matches that date. Check `status`.")
            return
        for g in targets:
            set_game_tm_event_id(g["id"], event_id)
            log_activity(g["id"], "tm_event_id_set", {"event_id": event_id})
        await message.channel.send(_confirm_summary(f"Saved TM link (#{event_id}) for", targets))
        return

    # --- sold <days/dates/all> ---
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

    # --- transferred <days/dates/all> ---  (before the 'transfer' disposition)
    if re.search(r"\btransferred\b", text):
        candidates = get_games_by_status(("to_transfer",))
        targets = _select(candidates, text)
        if not targets:
            await message.channel.send(
                "Nothing to mark transferred. Pick `transfer <days>` first, or check `status`."
            )
            return
        for g in targets:
            mark_transferred(g["id"])
            log_activity(g["id"], "transferred", {"source": "discord_reply"})
        await message.channel.send(_confirm_summary("Transferred", targets))
        return

    # --- listed <days/dates/all> ---  (exact 'listed', before the 'list' disposition)
    if re.search(r"\blisted\b", text):
        candidates = get_games_by_status(("to_list",))
        targets = _select(candidates, text)
        if not targets:
            await message.channel.send(
                "Nothing to mark listed. Pick `list <days>` first, or check `status`."
            )
            return
        for g in targets:
            mark_listed(g["id"], game_avg_price(g["day_of_week"]))
            log_activity(g["id"], "listed", {"source": "discord_reply"})
        await message.channel.send(_confirm_summary("Listed", targets))
        return

    # --- disposition: list / transfer (answer to "list or transfer?") ---
    if re.search(r"\blist\b", text) or re.search(r"\btransfer\b", text):
        await _handle_disposition(text, message, monday, sunday)
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
        await message.channel.send(_ask_disposition(games))
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
                continue  # don't touch games already being listed/transferred/sold
            if g["day_of_week"] in skip_days:
                update_game_status(g["id"], "skip")
                log_activity(g["id"], "skipped", {"source": "discord_reply", "matched_day": g["day_of_week"]})
            else:
                update_game_status(g["id"], "attending")
                log_activity(g["id"], "attending", {"source": "discord_reply"})

        games = get_games_for_week(monday, sunday)
        await message.channel.send(_ask_disposition(games))
        return

    # --- unrecognized ---
    await message.channel.send(
        "I didn't understand that. Reply `help` for a list of commands."
    )


async def _handle_disposition(text: str, message: discord.Message, monday: date, sunday: date) -> None:
    """Apply list/transfer choices, then send the matching prep + remind on leftovers."""
    week_games = get_games_for_week(monday, sunday)
    by_day = {g["day_of_week"]: g for g in week_games}
    pending = [g for g in week_games if g["status"] == "skip"]

    chosen: dict[int, str] = {}
    for action, target in _parse_dispositions(text):
        if target == "ALL":
            for g in pending:
                chosen[g["id"]] = action
        else:
            g = by_day.get(target)
            # works as the answer to the question (skip) and as a direct shortcut
            if g and g["status"] in ("upcoming", "attending", "skip"):
                chosen[g["id"]] = action

    if not chosen:
        await message.channel.send(
            "Tell me which way for each: `list thu, transfer fri`, or `list all` / `transfer all`."
        )
        return

    for game_id, action in chosen.items():
        update_game_status(game_id, action)
        log_activity(game_id, action, {"source": "discord_reply"})

    week_games = get_games_for_week(monday, sunday)
    to_list = [g for g in week_games if g["status"] == "to_list"]
    to_transfer = [g for g in week_games if g["status"] == "to_transfer"]

    reply = _build_confirmation(week_games)
    prep = build_prep_message(to_list)
    if prep:
        reply += "\n" + prep
    transfer = build_transfer_message(to_transfer)
    if transfer:
        reply += "\n" + transfer

    still = [g for g in week_games if g["status"] == "skip"]
    if still:
        reply += "\n\n⏳ Still need list/transfer for: " + ", ".join(_short(g) for g in still)

    await message.channel.send(reply)
