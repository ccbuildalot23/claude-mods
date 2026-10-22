#!/bin/bash
# Cloud environment setup script: installs Chris's mods into each new Claude Code cloud session.
claude plugin marketplace add ccbuildalot23/claude-mods || true
for m in switchboard blast-radius screen-share helper-desk chat-inventory replay-theater reflect cache-clock handoff brain-dump heads-up skins browser-peek crew; do
  claude plugin install "$m@chris-mods" || true
done
