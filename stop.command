#!/bin/zsh
# Tek tikla butun Tools uygulamalarini durdurur.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

run() {
    local label="$1"
    local script="$2"
    if [ ! -x "$script" ]; then
        echo "[skip] $label - script bulunamadi"
        return 0
    fi
    echo "[stop] $label"
    "$script" || true
}

run "Deployment Tracking"  "$ROOT_DIR/fordeveloper/stop.command"
run "Clipboard Keeper"     "$ROOT_DIR/clipboard-keeper/stop.command"
run "Display Agent"        "$ROOT_DIR/display-agent/stop.command"

echo "[stop] Tools Hub"
pkill -f "$ROOT_DIR/tools-hub/main.py" || true

echo ""
echo "Hepsi durduruldu."
