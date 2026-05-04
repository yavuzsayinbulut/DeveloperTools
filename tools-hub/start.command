#!/bin/zsh
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$APP_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python3"
STAMP_FILE="$VENV_DIR/.tools_hub_deps_ready"
LOG_FILE="$APP_DIR/tools-hub.log"

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

nohup "$PYTHON_BIN" "$APP_DIR/main.py" >> "$LOG_FILE" 2>&1 &
APP_PID=$!
disown

echo "Tools Hub baslatildi (PID: $APP_PID)."
echo "Bu pencereyi kapatabilirsiniz; uygulama menubar'da calismaya devam edecek."
echo "Loglar: $LOG_FILE"
