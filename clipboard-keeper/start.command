#!/bin/zsh
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$APP_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python3"
PIP_BIN="$VENV_DIR/bin/pip3"
STAMP_FILE="$VENV_DIR/.clipboard_keeper_deps_ready"

cd "$APP_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON_BIN" -m pip install --upgrade pip >/dev/null

if [ ! -f "$STAMP_FILE" ] || [ "requirements.txt" -nt "$STAMP_FILE" ]; then
  "$PIP_BIN" install -r requirements.txt
  touch "$STAMP_FILE"
fi

exec "$PYTHON_BIN" main.py
