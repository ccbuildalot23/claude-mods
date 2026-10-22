#!/usr/bin/env bash
PLIST="$HOME/Library/LaunchAgents/ink.labeau.mission-control.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Mission Control stopped. labeau-ops/scripts/mission_control.py and ~/.labeau/mission-control are left in place."
