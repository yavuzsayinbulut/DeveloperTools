#!/bin/zsh
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

pkill -f "$APP_DIR/tray.py" || true
pkill -f "$APP_DIR/app.py" || true
echo "For Developer durduruldu."
