#!/bin/bash
# Cloud environment setup script: installs Chris's mods into each new Claude Code cloud session.
claude plugin marketplace add ccbuildalot23/claude-mods || true
for m in switchboard blast-radius screen-share chat-inventory replay-theater reflect cache-clock handoff brain-dump heads-up skins browser-peek crew privacy-preflight outbox action-log bridge-inbox needs-you lightweek; do
  claude plugin install "$m@chris-mods" || true
done
