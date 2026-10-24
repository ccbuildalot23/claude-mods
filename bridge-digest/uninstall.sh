#!/bin/bash
# Stops the nightly bridge digest. The notes it wrote stay in the vault, and the app stays in ~/Applications.
LABEL="com.chris.bridge-digest"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
mv "$HOME/Library/LaunchAgents/$LABEL.plist" "$HOME/Library/LaunchAgents/$LABEL.plist.off" 2>/dev/null || true
echo "bridge-digest stopped."
