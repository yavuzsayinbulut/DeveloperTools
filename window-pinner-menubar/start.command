#!/bin/zsh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_BUNDLE="$APP_DIR/dist/WindowPinner.app"
APP_BIN="$APP_BUNDLE/Contents/MacOS/WindowPinner"
BUILD_SCRIPT="$APP_DIR/Scripts/build-app.sh"

needs_build=0
if [ ! -x "$APP_BIN" ]; then
  needs_build=1
elif [ "$APP_DIR/Package.swift" -nt "$APP_BIN" ]; then
  needs_build=1
elif find "$APP_DIR/Sources" -type f -newer "$APP_BIN" | grep -q .; then
  needs_build=1
elif [ "$BUILD_SCRIPT" -nt "$APP_BIN" ]; then
  needs_build=1
fi

if [ "$needs_build" -eq 1 ]; then
  "$BUILD_SCRIPT" >/dev/null
fi

exec "$APP_BIN"
