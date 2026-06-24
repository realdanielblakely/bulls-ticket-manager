#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# setup-on-box.sh — run ON the always-on Mac (after push-to-server.sh).
#
# Builds the venv, installs deps, creates the database from schedule.csv, and
# installs + loads the launchd LaunchAgent so the bot runs and auto-restarts.
# Idempotent — safe to re-run after each code push.
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"
LABEL="com.bullsticketmanager.app"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"

# 1. Python check (need 3.9+ for the type hints used in the code)
PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "python3 = $PYVER"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3,9) else 1)' \
  || { echo "✗ Need Python 3.9+. Install a newer python3 and re-run."; exit 1; }

# 2. Virtualenv + deps
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "✅ deps installed"

# 3. .env present?
[ -f .env ] || { echo "✗ No .env on the box. It should have been rsynced; check push-to-server.sh."; exit 1; }

# 4. Build/refresh the database from the committed schedule (event ids included)
.venv/bin/python -c "from app.database import create_tables; from app.schedule.csv_import import import_schedule; create_tables(); import_schedule()"
mkdir -p logs

# 5. Install + (re)load the LaunchAgent
mkdir -p "$HOME/Library/LaunchAgents"
sed "s#__APP_DIR__#$APP_DIR#g" "deploy/$LABEL.plist.template" > "$AGENT"
launchctl unload "$AGENT" 2>/dev/null || true
launchctl load "$AGENT"

echo ""
echo "✅ Loaded $LABEL"
echo "   status:   launchctl list | grep bulls-ticket-manager"
echo "   logs:     tail -f $APP_DIR/logs/bot.err.log"
echo "   stop:     launchctl unload $AGENT"
