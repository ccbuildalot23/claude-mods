#!/bin/bash
# Bridge digest installer. Safe to run again; it replaces its own launchd job.
# Nightly at 21:45 (after Grok's sweep) it writes the day's Bridge Digest and the Bridge Roster into
# Second Brain/Meta/Bridge/ in the vault. No AI, no network. Undo: bash bridge-digest/uninstall.sh
set -euo pipefail
cd "$(dirname "$0")"
DIR="$PWD"
LABEL="com.chris.bridge-digest"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
# launchd does not pass Python's Documents access to a job it starts, so the job runs inside a tiny app of its
# own, and only that app is granted the vault (the same pattern as voice-vault).
APP="$HOME/Applications/BridgeDigest.app"
PY=/usr/bin/python3

echo "Running tests..."
"$PY" -m unittest discover -s tests -q

mkdir -p state "$HOME/Library/LaunchAgents"
if [ ! -d "$APP" ]; then
  mkdir -p "$HOME/Applications"
  osacompile -o "$APP" -e "do shell script \"cd '$DIR' && $PY bridge_digest.py >> state/bridge-digest.log 2>&1\""
  /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$APP/Contents/Info.plist"  # no Dock icon
  codesign --force -s - "$APP"
fi

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$APP/Contents/MacOS/applet</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>45</integer></dict>
  <key>StandardOutPath</key><string>$DIR/state/launchd.out</string>
  <key>StandardErrorPath</key><string>$DIR/state/launchd.err</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

# First run now, while Chris is at the Mac, so macOS can ask about the Documents folder once.
: > state/launchd.err
launchctl kickstart -k "gui/$(id -u)/$LABEL"; sleep 8
if grep -q "Operation not permitted" state/launchd.err state/bridge-digest.log 2>/dev/null; then
  echo "macOS blocked the job from the vault in ~/Documents. Drag BridgeDigest from the Finder window into Full Disk Access and switch it on."
  open -R "$APP"; open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
  echo "Then run: launchctl kickstart -k gui/\$(id -u)/$LABEL"
else
  tail -2 state/bridge-digest.log 2>/dev/null || true
  echo "Installed $LABEL: runs nightly at 21:45. Open Second Brain/Meta/Bridge/ in Obsidian."
fi
