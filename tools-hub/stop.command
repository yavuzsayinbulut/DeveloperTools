#!/bin/zsh
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

pkill -f "$APP_DIR/main.py" || true
echo "Tools Hub durduruldu."
