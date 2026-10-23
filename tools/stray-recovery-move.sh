#!/bin/bash
# Move files agents filed into the stray ~/Documents/Desktop/Recovery back into
# the real vault, keeping each file's folder. Dry run unless you pass --go.
#   same path free     -> moved
#   same file already  -> stray copy set aside in ~/Documents/Stray Recovery Duplicates <date>
#   different file     -> moved beside it as "<name> (from stray).<ext>"
# Prints paths and counts only, never file contents.
set -u
SRC="${STRAY_SRC:-$HOME/Documents/Desktop/Recovery}"
DST="${VAULT_DST:-$HOME/Documents/Documents - Christopher’s MacBook Air/Desktop/Recovery}"
# Duplicates wait here for you to bin by hand (Terminal often cannot write to ~/.Trash).
TRASH="${STRAY_DUPES:-$HOME/Documents/Stray Recovery Duplicates $(date +%Y-%m-%d)}"
GO=0; [ "${1:-}" = "--go" ] && GO=1

[ -d "$SRC" ] || { echo "No stray folder at $SRC. Nothing to do."; exit 0; }
[ -d "$DST" ] || { echo "STOP: real vault not found at $DST"; exit 1; }

moved=0; dupes=0; renamed=0; newdirs=""
while IFS= read -r -d '' f; do
  rel="${f#"$SRC"/}"
  case "$(basename "$rel")" in .DS_Store) continue ;; esac
  dir="$(dirname "$rel")"
  [ -d "$DST/$dir" ] || case "$newdirs" in *"|$dir|"*) ;; *) newdirs="$newdirs|$dir|" ;; esac
  if [ ! -e "$DST/$rel" ]; then
    echo "MOVE    $rel"; moved=$((moved+1))
    [ $GO = 1 ] && mkdir -p "$DST/$dir" && mv -n "$f" "$DST/$rel"
  elif cmp -s "$f" "$DST/$rel"; then
    echo "DUPE    $rel  (already in vault, stray copy set aside)"; dupes=$((dupes+1))
    [ $GO = 1 ] && mkdir -p "$TRASH/$dir" && mv -n "$f" "$TRASH/$rel"
  else
    base="$(basename "$rel")"; stem="${base%.*}"; ext=""
    [ "$stem" != "$base" ] && ext=".${base##*.}"
    new="$dir/$stem (from stray)$ext"; new="${new#./}"
    echo "KEEP2   $rel  (vault has a different version, stray saved as: $(basename "$new"))"
    renamed=$((renamed+1))
    [ $GO = 1 ] && mv -n "$f" "$DST/$new"
  fi
done < <(find "$SRC" -type f -print0)

echo
echo "Summary: $moved to move, $dupes duplicates, $renamed kept side by side."
[ -n "$newdirs" ] && echo "Folders the real vault does not have yet (will be created):" &&
  printf '%s\n' "$newdirs" | tr '|' '\n' | sed '/^$/d' | sort -u | sed 's/^/  /'
if [ $GO = 1 ]; then
  find "$SRC" -name .DS_Store -delete
  find "$SRC" -depth -type d -empty -delete
  left=$(find "$SRC" -type f 2>/dev/null | wc -l | tr -d ' ')
  [ -d "$TRASH" ] && echo "Duplicates set aside in: $TRASH (check, then drag to the Trash)."
  echo "Done. Files left in stray: ${left:-0}. Real vault now has $(find "$DST" -type f | wc -l | tr -d ' ') files."
else
  echo "Dry run only. Nothing changed. Run again with --go to move."
fi
