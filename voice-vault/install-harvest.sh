#!/bin/bash
# Sunday harvest installer. Adds Apple's Vision reader to voice-vault's own Python,
# puts the Hierophant Lens and the share-candidates folder in labeau-ops (only if
# they are not there yet), and adds the `harvest` command. It does not touch the
# voice-vault launchd job or config.json.
set -euo pipefail
cd "$(dirname "$0")"
OPS="$HOME/Developer/labeau-ops"

[ -x .venv/bin/python ] || { echo "voice-vault is not installed yet (no .venv). Stop here and tell Claude."; exit 1; }
[ -d "$OPS/data" ] || { echo "Cannot find $OPS/data. Stop here and tell Claude."; exit 1; }

echo "Adding the Apple Vision reader (runs on this Mac only)..."
.venv/bin/pip install --quiet pyobjc-framework-Vision

echo "Running tests..."
.venv/bin/python -m unittest discover -s tests -q

echo "Checking the reader on a made-up page..."
.venv/bin/python - <<'EOF'
import diary_ocr
from pathlib import Path
lines = diary_ocr.ocr_lines(Path("templates/demo-page.png"))
assert any("river" in l for l in lines), lines
print("Reader OK:", len(lines), "lines read from the demo page")
EOF

mkdir -p "$OPS/data/share-candidates" "$OPS/data/hierophant-lens"
if [ -f "$OPS/data/hierophant-lens/hierophant-lens.md" ]; then
  echo "Hierophant Lens already there; left as is."
else
  cp templates/hierophant-lens.md "$OPS/data/hierophant-lens/hierophant-lens.md"
  echo "Hierophant Lens installed."
fi

if ! grep -q "alias harvest=" "$HOME/.zshrc" 2>/dev/null; then
  echo "alias harvest='cd ~/Developer/claude-mods/voice-vault && .venv/bin/python diary_harvest.py; cd - >/dev/null'" >> "$HOME/.zshrc"
  echo "Added the harvest command (open a new Terminal tab to use it)."
fi
echo "Done. Sunday: AirDrop your marked pages into ~/Voice Inbox, then type: harvest"
