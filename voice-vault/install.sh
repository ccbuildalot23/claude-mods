#!/bin/bash
# Voice-to-vault installer. Sets up local transcription and a launchd job that
# files new memos within a minute of them landing in ~/Voice Inbox.
set -euo pipefail
cd "$(dirname "$0")"
DIR="$PWD"
LABEL="com.chris.voice-vault"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
INBOX="$HOME/Voice Inbox"
MEMOS="$HOME/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
# launchd will not pass Python's Full Disk Access to a job it starts, so the job runs
# inside a tiny app of its own and Full Disk Access is granted to that app alone.
APP="$HOME/Applications/VoiceVault.app"

[ "$(uname -m)" = "arm64" ] || { echo "This Mac is not Apple silicon; mlx-whisper will not run. Stop here and tell Claude."; exit 1; }
command -v ffmpeg >/dev/null || { echo "Installing ffmpeg (audio decoder) with Homebrew..."; brew install ffmpeg; }

PY=/opt/homebrew/bin/python3; [ -x "$PY" ] || PY=/usr/bin/python3
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip mlx-whisper pyobjc-framework-Vision

echo "Running tests..."
.venv/bin/python -m unittest discover -s tests -q

mkdir -p "$INBOX" state
# Chris chose Voice Memos auto-sync (2026-10-22). Only memos recorded from now on are filed.
[ -f config.json ] || printf '{"watch_readonly": ["%s"], "watch_since": "%s"}\n' "$MEMOS" "$(date +%Y-%m-%dT%H:%M:%S)" > config.json

echo "Downloading the speech model once (about 1.6 GB, from Hugging Face; your audio never leaves this Mac)..."
.venv/bin/python -c "from huggingface_hub import snapshot_download as s; s('mlx-community/whisper-large-v3-turbo')" >/dev/null

if [ ! -d "$APP" ]; then
  mkdir -p "$HOME/Applications"
  osacompile -o "$APP" -e "do shell script \"cd '$DIR' && ./.venv/bin/python voice_vault.py\""
  /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$APP/Contents/Info.plist"  # no Dock icon
  codesign --force -s - "$APP"
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array>
    <string>$APP/Contents/MacOS/applet</string>
  </array>
  <key>WatchPaths</key><array><string>$INBOX</string><string>$MEMOS</string></array>
  <key>StartInterval</key><integer>600</integer>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
  <key>StandardOutPath</key><string>$DIR/state/launchd.out</string>
  <key>StandardErrorPath</key><string>$DIR/state/launchd.err</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

# The vault (~/Documents) and Voice Memos folder are guarded by macOS. Prove the job can reach both.
VAULT_INBOX="$(.venv/bin/python -c 'import voice_vault as v; print(v.load_config()["vault_inbox"])')"
mkdir -p "$VAULT_INBOX"
: > state/launchd.err
launchctl kickstart -k "gui/$(id -u)/$LABEL"; sleep 8
if grep -q "Operation not permitted" state/launchd.err 2>/dev/null || tail -1 state/voice-vault.log 2>/dev/null | grep -q "cannot read"; then
  echo "macOS blocked the background job from ~/Documents or Voice Memos. Drag VoiceVault from the Finder window into Full Disk Access and switch it on."
  open -R "$APP"; open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
  echo "Then run: launchctl kickstart -k gui/\$(id -u)/$LABEL"
else
  echo "Installed. Record in Voice Memos (or drop a file in \"$INBOX\"); start with 'Line' for the line bank, anything else stays private."
fi
