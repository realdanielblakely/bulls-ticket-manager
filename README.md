# 🐂 Bulls Ticket Manager

Personal automation for Durham Bulls season tickets. Each week a Discord bot asks
which home games you'll skip, then preps those tickets for resale on your
**Ticketmaster** account and tracks the season's P&L.

## How it works

1. **Sunday 10 AM ET** — the bot DMs you next week's home games.
2. You reply with the games you'll skip: `skip all`, `skip tue, thu`, or `attending all`.
3. For each skipped game the bot asks **list or transfer?** You answer
   (`list thu, transfer fri`).
4. The bot preps each one — a price + Ticketmaster link for games you're listing,
   just the link for games you're transferring.
5. You finish on Ticketmaster (about 15 seconds each), then confirm: `listed thu`,
   `transferred fri`. When a listed game sells, `sold thu` feeds your P&L.

> **Why not fully automatic?** Ticketmaster has no public API for individuals to
> list/transfer tickets, and automating its website risks the account that holds
> your real tickets. So the bot does the thinking and you tap the final button.
> See [`CLAUDE.md`](CLAUDE.md) for the full design.

## Commands

| Command | What it does |
|---------|--------------|
| `skip all` / `attending all` | Skip / keep every game next week |
| `skip tue, thu` | Skip specific days (rest = attending) |
| `list thu` / `transfer fri` | Answer "list or transfer?" (also `list all`, `list thu, transfer fri`) |
| `listed thu` | Confirm a game is live for resale on Ticketmaster |
| `sold thu` | Mark a listed game's tickets sold (feeds P&L) |
| `transferred fri` | Mark a game transferred to someone |
| `link 6/30 1459` | Save a game's Ticketmaster link |
| `status` / `help` | Status of next 7 games / command reference |

## Setup

```bash
cp .env.example .env          # fill in Discord token, seat info, pricing
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.main
```

The schedule lives in `schedule.csv` (75 home games, Mar 31 – Sep 13 2026) and is
synced into SQLite (`bulls.db`) on startup.

## Stack

Python 3.9 · discord.py · APScheduler · SQLite · FastAPI + Jinja2 dashboard.
