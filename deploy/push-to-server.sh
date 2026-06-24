#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# push-to-server.sh — copy this app to the always-on always-on Mac.
#
# Run from THIS Mac. rsyncs the repo to the box, shipping the .env (secrets)
# and schedule.csv, but NOT the local venv / database / logs — those are
# rebuilt/owned on the box. Safe to re-run to push code updates.
#
# SSH target follows the same convention as claude-os/push-graphs-to-server.sh:
#   default deploy@server.local, override with DEPLOY_REMOTE_SSH.
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)/"
REMOTE_SSH="${DEPLOY_REMOTE_SSH:-deploy@server.local}"
REMOTE_HOME="${DEPLOY_REMOTE_HOME:-/Users/deploy}"
REMOTE_DIR="$REMOTE_HOME/bulls-ticket-manager"

echo "Pushing $SRC -> $REMOTE_SSH:$REMOTE_DIR"
ssh -o ConnectTimeout=10 "$REMOTE_SSH" "mkdir -p '$REMOTE_DIR'"

# --delete keeps the remote in sync; excluded paths are protected from deletion,
# so the box's .venv / bulls.db / logs survive each push.
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'bulls.db' \
  --exclude 'bulls.db-*' \
  --exclude 'logs/' \
  --exclude 'My Events*' \
  -e 'ssh -o ConnectTimeout=10' \
  "$SRC" "$REMOTE_SSH:$REMOTE_DIR/"

echo "✅ pushed. Next: ssh $REMOTE_SSH, then  cd bulls-ticket-manager && ./deploy/setup-on-box.sh"
