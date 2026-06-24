# Bulls Ticket Manager — Project Context

## What This Is
Personal automation app for Durham Bulls AAA season tickets, with resale via the
owner's **Ticketmaster** account.

The loop:
1. **Sunday 10 AM ET** — Discord bot DMs the week's home games
2. Owner replies in plain text (`skip all`, `skip tue, thu`, `attending all`)
3. For skipped games, the bot sends a **listing-prep message**: suggested price
   per seat pair + a link to finish on Ticketmaster
4. Owner lists on TM (manual), then confirms `listed all` / `listed tue`
5. When it sells, owner confirms `sold tue` → feeds the P&L

## Why "Option A" (assisted manual, not full auto)
Ticketmaster has **no public API** for an individual to list tickets for resale —
listing is a manual action in the TM account/app. So the bot does all the
*thinking* (which games, what price) but the owner taps the final "list" button.
We deliberately avoided browser automation against TM (brittle + ToS risk to the
account that holds the real season tickets).

## Project Location
`the project directory`
Private GitHub repo under the **the owner's** account (personal, not the
`a separate` TMG account). Git identity is set repo-local.

## How to Run
```bash
cd bulls-ticket-manager
.venv/bin/python -m app.main      # venv created locally, gitignored
```
Bot name: **set in the Discord developer portal**

## Tech Stack
- Python **3.9.6** (system Python) — use `from __future__ import annotations`
  in any file with `X | Y` type hints
- discord.py 2.x, APScheduler, python-dotenv, pytz
- FastAPI + Jinja2 dashboard (season overview)
- SQLite (`bulls.db`) — plain `sqlite3`, no ORM
- CSV schedule (`schedule.csv`) — no Google Sheets

## Seat Configuration (two pairs, listed independently)
- **Pair 1 (lower bowl):** the configured lower-bowl seats
- **Pair 2 (upper bowl):** the configured upper-bowl seats
- Default list price: $35/pair, weekend premium: +$5 (Fri/Sat)
- All seat + pricing values come from `.env` (see `.env.example`)

## Status Flow
`upcoming → attending` (keep) **or** `upcoming → skip` (decided to sell)
`skip → listed` (owner confirms after listing on TM)
`listed → sold` (owner confirms sale; sold_price feeds P&L)

## Discord Commands (plain-text DMs)
- `skip all` / `attending all`
- `skip tue, thu` — skip specific days, rest auto-attending
- `listed all` / `listed tue, 4/2` — confirm games are live on TM
- `sold tue` — mark a listed game sold
- `link 4/2 <url>` — save the Ticketmaster per-game sell link (per date)
- `status` — next 7 games + statuses
- `help`
- Weekly cron: **Sunday 10:00 AM ET**

## Key Files
| File | Purpose |
|------|---------|
| `app/main.py` | Entry point |
| `app/config.py` | Settings from `.env` (seat pairs, pricing, TM url) |
| `app/database.py` | All SQLite queries + `mark_listed` / `mark_sold` |
| `app/discord_bot/weekly_prompt.py` | Sunday DM format + send |
| `app/discord_bot/reply_handler.py` | Parse skip/attend/listed/sold replies |
| `app/listing/prep.py` | Price suggestion + Ticketmaster prep message |
| `app/tasks/scheduler.py` | APScheduler cron setup |
| `app/dashboard/` | FastAPI + Jinja2 season view |
| `schedule.csv` | 75 home games (Mar 31 – Sep 13 2026) |

## Ticketmaster sell links (resolved)
The Bulls use Ticketmaster **Account Manager** (`am.ticketmaster.com/durhambulls/`,
NOT ticketmaster.com). Confirmed by testing:
- The **Sell flow has no URL** (in-page popup) — can't deep-link the sell form.
- Each game **does** have a deep-linkable page: `{base}/{event_id}`
  (e.g. `.../my-events/1459` = Jun 30). "Sell" is one tap from there.

So the bot stores each game's **event id** (`games.tm_event_id`), set via the
`link 6/30 1459` command (accepts a bare id or a full URL), and the prep message
links to `settings.event_url(event_id)`, falling back to the My Events list page
(`TICKETMASTER_BASE_URL`) when no id is saved. Known id: **Jun 30 = 1459**.

See [`TESTING.md`](TESTING.md); `python -m scripts.check_sell_links` lists which
games have an id saved.

## History
Originally designed around a StubHub seller API (`app/stubhub/`, never finished).
Pivoted to Ticketmaster when the owner gained the ability to resell directly
through the TM account. This repo is the fresh start; the StubHub code was dropped.
