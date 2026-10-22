#!/bin/bash
# Installs every mod in this folder as a user-scope Claude Code plugin.
cd "$(dirname "$0")"
claude plugin marketplace add "$PWD" 2>/dev/null || claude plugin marketplace update chris-mods
for m in switchboard blast-radius screen-share helper-desk chat-inventory replay-theater reflect cache-clock handoff brain-dump heads-up skins browser-peek crew; do
  claude plugin install "$m@chris-mods" || echo "  ($m: already installed or failed, see above)"
done
claude plugin list | grep -A4 "@chris-mods" | grep -E "@chris-mods|Status"
echo "Done. Restart Claude Code or run /reload-plugins, then type /mods."
