#!/bin/zsh
# Tek tikla SADECE Tools Hub'i acar. Diger uygulamalari Tools Hub icindeki
# "Start All" butonundan tek seferde baslatabilirsin.
# Hepsini birden durdurmak icin root stop.command'i kullan veya Tools Hub'in
# "Stop All" butonuna bas.

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "$ROOT_DIR/tools-hub/start.command" ]; then
    echo "Hata: $ROOT_DIR/tools-hub/start.command bulunamadi."
    exit 1
fi

echo "[start] Tools Hub"
"$ROOT_DIR/tools-hub/start.command"

echo ""
echo "Tools Hub baslatildi. Diger uygulamalar icin Tools Hub > Start All."
echo "Bu pencereyi kapatabilirsin."
