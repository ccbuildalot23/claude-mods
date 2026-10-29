#!/usr/bin/env bash
# Creates the Artist Support Team folders in the Recovery vault and copies the index notes in.
# Never overwrites a note that is already there.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VAULT="${LABEAU_VAULT:-$(ls -d "$HOME"/Documents/*/Desktop/Recovery 2>/dev/null | head -1)}"
[ -d "$VAULT" ] || { echo "Recovery vault not found; set LABEAU_VAULT=/path/to/Recovery"; exit 1; }
TEAM="$VAULT/Professional Knowledge/Artist Support Team"
mkdir -p "$TEAM/LaBeau Lane" "$TEAM/Artist Lane" "$TEAM/Shared"
added=0
while IFS= read -r -d '' src; do
  rel="${src#"$HERE/vault-seed/"}"
  dst="$TEAM/$rel"
  if [ -e "$dst" ]; then echo "kept   $rel"; else cp "$src" "$dst"; echo "added  $rel"; added=$((added+1)); fi
done < <(find "$HERE/vault-seed" -type f -name '*.md' -print0)
# Notes the cloud team wrote for the vault wait in ~/Developer/artist-team-inbox/<Lane>/ until this runs.
INBOX="${ARTIST_TEAM_INBOX:-$HOME/Developer/artist-team-inbox}"
if [ -d "$INBOX" ]; then
  while IFS= read -r -d '' src; do
    rel="${src#"$INBOX/"}"
    dst="$TEAM/$rel"
    mkdir -p "$(dirname "$dst")"
    if [ -e "$dst" ]; then echo "kept   $rel (inbox copy left in place)"; else cp "$src" "$dst"; echo "filed  $rel"; added=$((added+1)); fi
  done < <(find "$INBOX" -type f -name '*.md' -print0)
fi
echo "Artist Support Team ready at: $TEAM ($added new notes)"
