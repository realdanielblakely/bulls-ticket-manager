# Testing the Ticketmaster sell link

Ticketmaster has no public API to list tickets for resale, so the bot can't
list for you. The best it can do is hand you a link that opens **straight to
the sell screen for a specific game** — so listing is one tap instead of
digging through your account. This is the one piece we couldn't confirm from
code, because it needs your logged-in Ticketmaster account.

Here's the 2-minute test to find out if that link exists and works.

## The test (do this once)

1. On your phone or computer, **log in to Ticketmaster** (the account that holds
   the Bulls tickets).
2. Go to your tickets and start listing **one** upcoming Bulls game for resale —
   tap **Sell**, but you don't have to finish.
3. Look at the address bar (or the share/copy-link option in the app) and
   **copy the URL** of that sell screen.
4. Send it to me, or save it to the bot with one Discord message:

   ```
   link 4/2 https://www.ticketmaster.com/...the-url-you-copied...
   ```

   (Use the real date and the real URL.)

## What we learn

- **If that link, when re-opened later, lands back on the sell screen** → 🎉
  per-game deep links work. We can save one per game and every weekly prep
  message will link you straight to the right sell screen.
- **If it just bounces to your account home or a login page** → deep links
  don't survive, and we fall back to the generic "My Events" page
  (`TICKETMASTER_SELL_URL` in `.env`). Still useful, just one extra tap.

## Checking what's saved

Any time, run this from the repo root to see which games have a real saved link
vs. the generic page:

```bash
.venv/bin/python -m scripts.check_sell_links        # next 10 games
.venv/bin/python -m scripts.check_sell_links 30     # next 30 games
```

## Notes

- A saved link is **per game** (each game has its own sell screen), so the
  `link` command targets a single date: `link 4/2 <url>`.
- If most games share the same URL pattern with just an event ID swapped, tell
  me — we can switch to auto-generating links from the schedule instead of
  saving each one by hand.
