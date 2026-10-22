#!/bin/bash
# Build (where needed) and open one of the apps: ./apps/open.sh line-bank | reel-review | keep-or-drop | grid-preview | brand-deals
set -e
cd "$(dirname "$0")"
APP="$1"
OUT="$HOME/Developer/claude-mods/apps-out"
case "$APP" in
  line-bank|keep-or-drop|grid-preview)
    python3 "$APP/build.py"
    open "$OUT/$APP.html" ;;
  reel-review|brand-deals)
    open "$APP/page.html" ;;
  *)
    echo "Which app? line-bank, reel-review, keep-or-drop, grid-preview, brand-deals"; exit 1 ;;
esac
