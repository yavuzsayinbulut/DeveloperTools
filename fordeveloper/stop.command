#!/bin/zsh
set -e

pkill -f "fordeveloper.*app.py|app.py" || true
