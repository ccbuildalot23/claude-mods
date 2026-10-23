#!/bin/bash
# Journal gate installer (diary-to-brand pathway v2). Reads journal page photos from
# ~/Voice Inbox overnight on this Mac, fills the Brand Message Library, and sends the
# Monday docket. Leaves the voice-vault job and config.json alone.
# Undo: launchctl bootout gui/$(id -u)/ink.labeau.journal-gate && rm ~/Library/LaunchAgents/ink.labeau.journal-gate.plist
set -euo pipefail
cd "$(dirname "$0")"
DIR="$PWD"
OPS="$HOME/Developer/labeau-ops"
LENS="$OPS/data/hierophant-lens/hierophant-lens.md"
LABEL="ink.labeau.journal-gate"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

[ -x .venv/bin/python ] || { echo "voice-vault is not installed yet (no .venv). Stop here and tell Claude."; exit 1; }
[ -d "$OPS/data" ] || { echo "Cannot find $OPS/data. Stop here and tell Claude."; exit 1; }

.venv/bin/pip install --quiet pyobjc-framework-Vision
echo "Running tests..."
.venv/bin/python -m unittest discover -s tests -q

mkdir -p "$OPS/data/share-candidates" "$OPS/data/hierophant-lens" "$HOME/LaBeau-Assets/Journal Pages" "$HOME/Voice Inbox" state/gate
touch ../config/name-roles.txt ../config/name-ok.txt
if [ ! -f "$LENS" ] || [ "$(grep -c '(empty until' "$LENS")" = "2" ]; then
  [ -f "$LENS" ] && cp "$LENS" "state/gate/hierophant-lens.before-v2.md"
  cp templates/hierophant-lens.md "$LENS"
  echo "Hierophant Lens updated to v2."
else
  echo "Hierophant Lens already holds your lines; left as is."
fi

echo "Reading a made-up page with the real reader..."
.venv/bin/python journal_gate.py selftest

echo "Checking the mail login (the docket reads your replies)..."
.venv/bin/python journal_gate.py check || echo "Mail check failed: the docket will still send; tell Claude so replies can be fixed."

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>ProgramArguments</key><array>
    <string>$DIR/.venv/bin/python</string><string>$DIR/journal_gate.py</string><string>run</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>$DIR/state/gate/launchd.out</string>
  <key>StandardErrorPath</key><string>$DIR/state/gate/launchd.err</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

python3 - <<'PY'
import os, re
p = os.path.expanduser("~/.zshrc")
s = open(p).read() if os.path.exists(p) else ""
new = "alias harvest='~/Developer/claude-mods/voice-vault/.venv/bin/python ~/Developer/claude-mods/voice-vault/journal_gate.py now'"
s = re.sub(r"(?m)^alias harvest=.*$", new, s) if "alias harvest=" in s else s.rstrip("\n") + "\n" + new + "\n"
open(p, "w").write(s)
PY
echo "Done. Sunday: drop the week's journal photos in ~/Voice Inbox. The gate reads them overnight; the docket comes Monday 7 am."
