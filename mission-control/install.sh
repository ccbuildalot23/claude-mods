#!/usr/bin/env bash
# Mission Control installer. Safe to run again; it replaces its own launchd job.
set -euo pipefail
MC="$(cd "$(dirname "$0")" && pwd)"
OPS="$HOME/Developer/labeau-ops"
PY="$OPS/.venv/bin/python"
LABEL="ink.labeau.mission-control"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
[ -x "$PY" ] || { echo "labeau-ops venv python not found at $PY"; exit 1; }
STATE="$HOME/.labeau/mission-control"
mkdir -p "$STATE" "$HOME/Library/LaunchAgents"
cp "$MC/mission_control.py" "$OPS/scripts/mission_control.py"
SCRIPT="$OPS/scripts/mission_control.py"

TIMES=""
for h in $(seq 0 23); do
  for m in 5 35; do
    TIMES="$TIMES<dict><key>Hour</key><integer>$h</integer><key>Minute</key><integer>$m</integer></dict>"
  done
done

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$SCRIPT</string></array>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string><key>PYTHONPATH</key><string>$OPS/scripts</string></dict>
<key>WorkingDirectory</key><string>$OPS</string>
<key>RunAtLoad</key><true/>
<key>StartCalendarInterval</key><array>$TIMES</array>
<key>StandardOutPath</key><string>$STATE/launchd.log</string>
<key>StandardErrorPath</key><string>$STATE/launchd.log</string>
</dict></plist>
PL

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "installed $LABEL (runs at :05 and :35 every hour)"

MAP="$OPS/data/harness_map.csv"
if [ -f "$MAP" ] && ! grep -q "routine:launchd:mission-control" "$MAP"; then
  printf '%s\n' 'routine:launchd:mission-control,routine,mission-control,scripts/mission_control.py; launchd ink.labeau.mission-control at :05 and :35,Draft,Draft,outbound,Draft,2026-10-22,0,mission-control;mission_control,"Every 30 min: read-only check of the daily email, captions, assets, tomorrow holds and launchd jobs. Writes status to ~/.labeau/mission-control and Drive (LaBeau-Assets/mission-control) for the phone page. Emails Chris only when something is red at 06:35, 16:05 or 16:35. Never posts or writes copy."' >> "$MAP"
  echo "harness map row added: routine:launchd:mission-control"
fi

PYTHONPATH="$OPS/scripts" "$PY" "$SCRIPT" --print --no-alert
