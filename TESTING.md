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

## How to give the bot a game's link

When you're on a game's page, copy the number at the end of the URL (or the whole
URL) and send the bot:

```
link 6/30 1459
```
or
```
link 6/30 https://am.ticketmaster.com/durhambulls/my-events/1459
```

Both save event id `1459` for the June 30 game. After that, the weekly prep
message links you straight to that game's page.

## Getting the rest of the ids

You only need ids for games you actually sell, and the weekly prompt surfaces
just a handful at a time — so the easiest path is to add one with `link` each
week as games come up. If you'd rather do them all at once, open the My Events
list and grab the trailing number from each game's page; or send me the list and
I'll bulk-load them.

(Known so far: **Jun 30 = 1459**, already saved.)

## Checking what's saved

From the repo root:

```bash
.venv/bin/python -m scripts.check_sell_links        # next 10 games
.venv/bin/python -m scripts.check_sell_links 30     # next 30 games
```

Games with a saved id show a direct game-page link; the rest fall back to the My
Events list page (`TICKETMASTER_BASE_URL` in `.env`).
