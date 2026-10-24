#!/bin/bash
# Installs every mod in this folder as a user-scope Claude Code plugin.
cd "$(dirname "$0")"
claude plugin marketplace add "$PWD" 2>/dev/null || claude plugin marketplace update chris-mods
# helper-desk was folded into crew on Oct 24, 2026; take the old copy out if it is still installed.
claude plugin uninstall "helper-desk@chris-mods" 2>/dev/null || true
for m in switchboard blast-radius screen-share chat-inventory replay-theater reflect cache-clock handoff brain-dump heads-up skins browser-peek crew privacy-preflight outbox action-log bridge-inbox needs-you lightweek; do
  claude plugin install "$m@chris-mods" || echo "  ($m: already installed or failed, see above)"
done
claude plugin list | grep -A4 "@chris-mods" | grep -E "@chris-mods|Status"
echo "Done. Restart Claude Code or run /reload-plugins, then type /mods."
