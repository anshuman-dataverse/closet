#!/bin/sh
# Install or reinstall the Closet worker as a launchd agent (starts at login, restarts on crash).
# Usage: worker/launchd/install.sh            install / reload
#        worker/launchd/install.sh uninstall  remove
set -eu
LABEL=com.closet.worker
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [ "${1:-}" = "uninstall" ]; then rm -f "$DEST"; echo "Removed $LABEL"; exit 0; fi
[ -f "$DIR/.env" ] || { echo "Missing $DIR/.env (copy .env.example first)"; exit 1; }
UV="$(command -v uv)"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s#__WORKER_DIR__#$DIR#g" -e "s#__UV__#$UV#g" -e "s#__HOME__#$HOME#g" \
  "$DIR/launchd/$LABEL.plist" > "$DEST"
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "Installed $LABEL. Logs: ~/Library/Logs/closet-worker.log"
