#!/bin/zsh
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$APP_DIR/.." && pwd)"
VENV_DIR="$APP_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python3"
STAMP_FILE="$VENV_DIR/.deps_ready"
APP_LOG="$APP_DIR/delivery-radar.log"
TRAY_LOG="$APP_DIR/delivery-radar-tray.log"

ROOT_VENV="$ROOT_DIR/.venv"
ROOT_PYTHON="$ROOT_VENV/bin/python3"

# Recreate venv if it's missing or its python is broken (e.g. moved folder
# leaves stale shebangs/symlinks).
ensure_venv() {
    local venv="$1"
    local py="$venv/bin/python3"
    if [ ! -x "$py" ] || ! "$py" -c "import sys" >/dev/null 2>&1; then
        rm -rf "$venv"
        python3 -m venv "$venv"
    fi
}

cd "$APP_DIR"

ensure_venv "$VENV_DIR"
"$PYTHON_BIN" -m pip install --upgrade pip >/dev/null

if [ ! -f "$STAMP_FILE" ] || [ "requirements.txt" -nt "$STAMP_FILE" ]; then
  "$PYTHON_BIN" -m pip install -r requirements.txt
  touch "$STAMP_FILE"
fi

ensure_venv "$ROOT_VENV"
if ! "$ROOT_PYTHON" -c "import PySide6" >/dev/null 2>&1; then
  "$ROOT_PYTHON" -m pip install --upgrade pip >/dev/null
  "$ROOT_PYTHON" -m pip install "PySide6>=6.5"
fi

nohup "$PYTHON_BIN" "$APP_DIR/app.py" >> "$APP_LOG" 2>&1 &
APP_PID=$!
disown

nohup "$ROOT_PYTHON" "$APP_DIR/tray.py" >> "$TRAY_LOG" 2>&1 &
TRAY_PID=$!
disown

echo "Delivery Radar baslatildi (server PID: $APP_PID, tray PID: $TRAY_PID)."
echo "Bu pencereyi kapatabilirsiniz; uygulama menubar'dan erisilebilir."
echo "Loglar: $APP_LOG, $TRAY_LOG"
