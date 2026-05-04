#!/bin/zsh
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT_DIR/tools-hub"
VENV_DIR="$ROOT_DIR/.venv"
STAMP_FILE="$VENV_DIR/.tools_hub_deps_ready"

cd "$APP_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip >/dev/null

if [ ! -f "$STAMP_FILE" ] || [ "requirements.txt" -nt "$STAMP_FILE" ]; then
  pip install -r requirements.txt
  touch "$STAMP_FILE"
fi

exec python main.py
