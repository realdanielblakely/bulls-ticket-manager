"""
Build and send the weekly game-list DM.

Called by the Sunday cron job (tasks/scheduler.py) and also available
to trigger manually for testing.
"""

import logging
from datetime import date

from app.database import (
    get_upcoming_games_for_week,
    log_activity,
    next_week_bounds,
)

log = logging.getLogger(__name__)


def _format_prompt(games: list) -> str:
    lines = ["🐂 **Durham Bulls — Games This Week**\n"]
    for g in games:
        # Short date like "Tue 3/31"
        d = date.fromisoformat(g["date"])
        short_day = g["day_of_week"][:3]
        short_date = f"{d.month}/{d.day}"
        lines.append(f"  {short_day} {short_date}  vs {g['opponent']}  {g['time']}")

    lines.append("")
    lines.append("Reply with days to **SKIP** (I'll ask list or transfer for each).")
    lines.append('Examples: `skip all` / `skip Tue, Thu` / `attending all`')
    return "\n".join(lines)


async def send_weekly_prompt() -> None:
    """Query next week's games and DM the owner."""
    from app.discord_bot.bot import send_dm

    monday, sunday = next_week_bounds()
    games = get_upcoming_games_for_week(monday, sunday)

    if not games:
        log.info("No upcoming games next week (%s – %s), skipping prompt", monday, sunday)
        await send_dm(f"🐂 No Bulls home games next week ({monday.strftime('%b %d')} – {sunday.strftime('%b %d')}). Enjoy your week!")
        return

    message = _format_prompt(games)
    await send_dm(message)

    for g in games:
        log_activity(g["id"], "prompted", {"week_start": monday.isoformat()})

    log.info("Sent weekly prompt for %d game(s) (%s – %s)", len(games), monday, sunday)
