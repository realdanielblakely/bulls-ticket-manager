# 🐂 Bulls Ticket Manager

Personal automation for Durham Bulls season tickets. Each week a Discord bot asks
which home games you'll skip, then preps those tickets for resale on your
**Ticketmaster** account and tracks the season's P&L.

## How it works

1. **Sunday 10 AM ET** — the bot DMs you next week's home games.
2. You reply with the games to skip: `skip all`, `skip tue, thu`, or `attending all`.
3. For each skipped game the bot replies with a **listing prep**: the suggested
   price for each seat pair plus a link to finish on Ticketmaster.
4. You list them on TM (about 15 seconds each) and reply `listed all`.
5. When they sell, reply `sold tue` and the sale feeds your season P&L.

> **Why not fully automatic?** Ticketmaster has no public API for individuals to
> list tickets for resale, and automating its website risks the account that
> holds your real tickets. So the bot does the thinking and you tap the final
> button. See [`CLAUDE.md`](CLAUDE.md) for the full design.

## Commands

| Command | What it does |
|---------|--------------|
| `skip all` / `attending all` | Sell / keep every game next week |
| `skip tue, thu` | Sell specific days (rest = attending) |
| `listed all` / `listed tue, 4/2` | Confirm games are live on Ticketmaster |
| `sold tue` | Mark a listed game's tickets sold |
| `status` | Show the next 7 games and their statuses |
| `help` | Command reference |

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
