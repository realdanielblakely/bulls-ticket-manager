# Running on the always-on Mac

The bot runs on the always-on always-on Mac (`deploy@server.local`)
instead of a paid host. macOS keeps it alive with **launchd**: it starts when the
`deploy` user is logged in and restarts itself if it ever crashes.

## One-time setup

**1. From THIS Mac — push the code:**
```bash
cd bulls-ticket-manager
./deploy/push-to-server.sh
```
This rsyncs the app (including your `.env` secrets and `schedule.csv` with the
event ids) to `/Users/deploy/bulls-ticket-manager`. It does NOT copy the local
venv or database — those are built fresh on the box.

**2. On the box — build and start it:**
```bash
ssh deploy@server.local
cd bulls-ticket-manager
./deploy/setup-on-box.sh
```
That creates the venv, installs deps, builds the database from `schedule.csv`,
and loads the launchd job. The bot is now running.

**3. Confirm it's up:**
```bash
launchctl list | grep bulls-ticket-manager      # shows a PID if running
tail -f logs/bot.err.log                         # watch startup logs
```

## Updating later (after code changes)

```bash
# from this Mac
./deploy/push-to-server.sh
# then on the box
ssh deploy@server.local 'cd bulls-ticket-manager && ./deploy/setup-on-box.sh'
```
`setup-on-box.sh` reloads the launchd job, so the new code takes effect.

## Two things to watch

- **Only run the bot in ONE place.** Discord allows a bot token one live
  connection. Once it's on the box, don't also `python -m app.main` on this Mac —
  they'd fight over the connection. (Quick local tests are fine if the box copy
  is stopped first.)
- **The MacBook must not sleep**, or the bot goes offline. It may already run
  24/7, so this is probably handled; if not, keep it awake with:
  ```bash
  sudo pmset -a sleep 0 disablesleep 1     # or run under `caffeinate -s`
  ```

## Stop / start / remove

```bash
AGENT=~/Library/LaunchAgents/com.bullsticketmanager.app.plist
launchctl unload "$AGENT"     # stop
launchctl load   "$AGENT"     # start
rm "$AGENT"                   # remove for good (after unloading)
```

## Note on always-on hosting

Nothing here is host-specific except the SSH target and paths — if you ever
move to Railway/Render, the app itself (`python -m app.main`) runs the same way;
you'd just supply `.env` as host environment variables instead of a file.
