#!/bin/sh
# Render one HTML file to PNG. Usage: shot.sh <html> <png> [width] [height]
# Tries macOS Chrome, then a Linux Chrome/Chromium, then Python Playwright.
W=${3:-1200}; H=${4:-800}
ABS="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
BIN=""
for B in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" google-chrome google-chrome-stable chromium chromium-browser; do
  if [ -x "$B" ] || command -v "$B" >/dev/null 2>&1; then BIN="$B"; break; fi
done
if [ -n "$BIN" ]; then
  P=$(mktemp -d "${TMPDIR:-/tmp}/dsshot.XXXXXX")
  perl -e 'alarm 60; exec @ARGV' "$BIN" --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
    --no-first-run --user-data-dir="$P" --window-size="$W,$H" --virtual-time-budget=4000 \
    --screenshot="$2" "file://$ABS" >/dev/null 2>&1
  rm -rf "$P"
else
  python3 - "$ABS" "$2" "$W" "$H" <<'PY' || { echo "FAIL no browser (pip install playwright && python3 -m playwright install --with-deps chromium)"; exit 2; }
import sys
from playwright.sync_api import sync_playwright
src, out, w, h = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": w, "height": h})
    pg.goto("file://" + src); pg.wait_for_timeout(1500); pg.screenshot(path=out); b.close()
PY
fi
[ -s "$2" ] && echo "OK $2" || { echo "FAIL"; exit 1; }
