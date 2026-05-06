#!/bin/zsh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BIN="$APP_DIR/dist/WindowPinner.app/Contents/MacOS/WindowPinner"

osascript -e 'tell application id "local.windowpinner.menubar" to quit' >/dev/null 2>&1 || true
sleep 1

if pgrep -f "$APP_BIN" >/dev/null 2>&1; then
  pkill -f "$APP_BIN" || true
fi
