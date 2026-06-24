# Ticketmaster sell links — what we found

The Bulls don't use `ticketmaster.com`. They use Ticketmaster's **Account
Manager** team portal: `https://am.ticketmaster.com/durhambulls/`.

What the testing turned up:

- **All your tickets:** `https://am.ticketmaster.com/durhambulls/my-events`
- **One game (e.g. Tue Jun 30):** `https://am.ticketmaster.com/durhambulls/my-events/1459`
  — every game has its own page with a stable numeric **event id**.
- **The Sell flow has no URL.** Clicking *Sell*, picking tickets, and setting a
  price all happen in an in-page popup — the address bar never changes. So we
  cannot link directly to the sell form.

**Conclusion:** we link to the **game's page** (which we *can* deep-link), and
*Sell* is one tap from there. The bot stores each game's event id and builds the
link as `{base}/{event_id}`.

## Current status: all ids loaded

Every remaining home game (Jun 30 → Sep 13 2026, 33 games) already has its event
id saved in `schedule.csv` and the database, so the weekly prep message links
straight to each game's page. Nothing to do for the rest of this season.

## Refreshing ids (e.g. next season, or if links change)

1. In a logged-in browser, open
   `https://am.ticketmaster.com/durhambulls/my-events`
2. Save it: **File → Save Page As → "Webpage, Complete"** into the repo folder.
3. Run the loader (parses the page, writes ids into `schedule.csv`, syncs the DB):
   ```bash
   .venv/bin/python -m scripts.load_event_ids "My Events _ Durham Bulls.html"
   ```
   It's idempotent and never touches skip/attend/sold decisions.

## Fixing a single game by hand

If one game's id is missing or wrong, set it from Discord — copy the number at
the end of that game's URL (or paste the whole URL):

```
link 6/30 1459
link 6/30 https://am.ticketmaster.com/durhambulls/my-events/1459
```

## Checking what's saved

From the repo root:

```bash
.venv/bin/python -m scripts.check_sell_links        # next 10 games
.venv/bin/python -m scripts.check_sell_links 30     # next 30 games
```

Games with a saved id show a direct game-page link; the rest fall back to the My
Events list page (`TICKETMASTER_BASE_URL` in `.env`).
