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

## Status Flow (with the list/transfer action gate)
`upcoming → attending` (keep)
`upcoming → skip` (not attending — awaiting list/transfer decision)
`skip → to_list → listed → sold`  (resale; sold_price feeds P&L)
`skip → to_transfer → transferred` (handed to someone; no revenue by default)

Two-step weekly decision: (1) attend or skip, then (2) for each skipped game the
bot asks **list or transfer?** and the owner answers. Consign is intentionally
not implemented (owner uses only list + transfer).

## Discord Commands (plain-text DMs)
- `skip all` / `attending all` / `skip tue, thu` — step 1 (attend vs not)
- `list thu` / `transfer fri` / `list all` / `transfer all` / `list thu, transfer fri`
  — step 2 (answer to "list or transfer?"; also works as a direct shortcut)
- `listed tue, 7/2` — confirm a to_list game is live on TM
- `sold tue` — mark a listed game sold (feeds P&L)
- `transferred fri` — mark a to_transfer game sent
- `link 6/30 1459` — save a game's TM event id (per date)
- `status` — next 7 games + statuses
- `help`

Command parse order matters: `sold` / `transferred` / `listed` are matched before
the `transfer` / `list` disposition verbs (substring overlap).
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

So the bot stores each game's **event id** (`games.tm_event_id`) and the prep
message links to `settings.event_url(event_id)`, falling back to the My Events
list page (`TICKETMASTER_BASE_URL`) when no id is saved.

Ids live in `schedule.csv` (committed source of truth, `tm_event_id` column) and
`csv_import` syncs them into the DB without disturbing status. All 33 remaining
2026 home games (Jun 30 – Sep 13) are loaded. They are **not** sequential by date
(Jun 30 = 1459, Jul 1 = 1416), so they must be captured, not computed.

To (re)load from a saved My Events page:
`python -m scripts.load_event_ids "My Events _ Durham Bulls.html"`.
To fix one game ad hoc: `link 6/30 1459` in Discord (bare id or full URL).
`python -m scripts.check_sell_links` lists which games have an id. See
[`TESTING.md`](TESTING.md). Saved `.html` pages are gitignored.

## History
Originally designed around a StubHub seller API (`app/stubhub/`, never finished).
Pivoted to Ticketmaster when the owner gained the ability to resell directly
through the TM account. This repo is the fresh start; the StubHub code was dropped.
