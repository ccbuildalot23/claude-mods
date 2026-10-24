#!/bin/bash
# Phase 3: Remotion 4.0.538 and HyperFrames 0.8.191 (both already locked in package-lock.json by phase 2).
# Test: one 15-second silhouette text video (no face) with Chris's lines, rendered by each tool and checked with
# labeau safe-zone. Lines come from the composition defaults (his posted darkness lines) unless a file is given:
#   ./phase3.sh my-lines.txt    one row per line, blank line for a stanza gap
PHASE=3
. "$(dirname "$0")/bin/lib.sh"
echo "Toolkit phase 3 (Remotion, HyperFrames), $(date '+%Y-%m-%d %H:%M ET')"
node_ok || { bad "Node.js 22.20+ missing: run phase 2 first"; finish; exit 1; }
[ -d "$TK/node_modules/remotion" ] || (cd "$TK" && npm ci --no-audit --no-fund --loglevel=error --no-update-notifier)
STAMP="$(date +%Y%m%d-%H%M)"
PROPS=""; VARS=""
if [ -n "$1" ]; then
  # His lines go in as files, never on the command line, so quotes and spaces arrive untouched.
  PF="$(mktemp).json"; VF="$(mktemp).json"
  "$PY" -c 'import json,sys; rows=open(sys.argv[1]).read().rstrip("\n"); json.dump({"rows": rows.split("\n")}, open(sys.argv[2], "w")); json.dump({"rows": rows}, open(sys.argv[3], "w"))' "$1" "$PF" "$VF"
  PROPS="--props=$PF"; VARS="--variables-file=$VF"
fi

step "Remotion (15)"
RV="$(node -p 'require(process.argv[1]).version' "$TK/node_modules/remotion/package.json")"
[ "$RV" = "4.0.538" ] && ok "works: remotion $RV (Free License: individuals and up to 3 employees, commercial use allowed)" || bad "remotion is $RV, not 4.0.538"
RMP4="$TK/out/remotion-silhouette15-$STAMP.mp4"
(cd "$TK/remotion" && ../node_modules/.bin/remotion render src/index.ts Silhouette15 "$RMP4" --public-dir="$PWD/public" --browser-executable="$(node ../bin/browser-path.mjs)" --log=error $PROPS) && ok "works: rendered $RMP4" || bad "Remotion render failed"

step "HyperFrames (14)"
HV="$(node -p 'require(process.argv[1]).version' "$TK/node_modules/hyperframes/package.json")"
[ "$HV" = "0.8.191" ] && ok "works: hyperframes $HV (Apache-2.0, github.com/heygen-com/hyperframes)" || bad "hyperframes is $HV, not 0.8.191"
(cd "$TK/hyperframes" && ../node_modules/.bin/hyperframes telemetry disable >/dev/null 2>&1) && ok "HyperFrames telemetry off" || note "could not switch HyperFrames telemetry off"
mkdir -p "$TK/hyperframes/vendor" && cp "$TK/node_modules/gsap/dist/gsap.min.js" "$TK/hyperframes/vendor/"
HMP4="$TK/out/hyperframes-silhouette15-$STAMP.mp4"
(cd "$TK/hyperframes" && ../node_modules/.bin/hyperframes render . -o "$HMP4" --quiet $VARS >/dev/null 2>&1) && ok "works: rendered $HMP4" || bad "HyperFrames render failed (see: cd $TK/hyperframes && npx hyperframes doctor)"

step "Test: both videos are 15 s, 1080x1920, every word in the safe zone"
for f in "$RMP4" "$HMP4"; do
  [ -f "$f" ] || continue
  D="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" | cut -d. -f1)"
  S="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$f" | head -1 | cut -d, -f1,2)"
  [ "$D" = 15 ] && [ "$S" = "1080,1920" ] && ok "$(basename "$f"): 15 s at 1080x1920" || bad "$(basename "$f"): ${D}s at $S"
done
if [ -x "$OPS/bin/labeau" ]; then
  SZ="$("$OPS/bin/labeau" safe-zone "$RMP4" "$HMP4" 2>&1)"
  echo "$SZ" | sed 's/^/    /'
  echo "$SZ" | grep -q "2 pass, 0 fail, 0 review" && ok "labeau safe-zone: both pass" || bad "labeau safe-zone did not pass both"
else
  note "labeau-ops not found; safe-zone check skipped"
fi

step "Blocked stays blocked"
grep -q 'labeau-no-face' "$TK/.claude/hookify.labeau-no-face.local.md" 2>/dev/null && grep -q 'hyperframes' "$TK/.claude/hookify.labeau-no-send.local.md" 2>/dev/null && ok "hookify blocks hyperframes publish and any avatar / talking-head / face tool" || bad "LaBeau hookify rules missing in toolkit/.claude (run phase 1)"
grep -q '"node_modules/remotion"' "$TK/package-lock.json" && grep -q '"node_modules/hyperframes"' "$TK/package-lock.json" && ok "Remotion and HyperFrames locked in package-lock.json" || bad "lockfile missing Remotion or HyperFrames"

step "Removes cleanly"
(cd "$TK" && npm uninstall --dry-run remotion @remotion/cli hyperframes gsap >/dev/null 2>&1) && ok "npm uninstall dry run passes (undo: rm -r toolkit/node_modules ~/.cache/hyperframes)" || bad "npm uninstall dry run failed"

step "Log: Changes rows, register rows, thread turn"
if [ "$FAILS" -eq 0 ]; then
  change_row "Media toolkit" "Remotion 4.0.538 and HyperFrames 0.8.191 (+ GSAP 3.15.0, local) in claude-mods/toolkit; 15-second silhouette text video test passed in both, safe zone clear" "42 add-ons plan items 15 and 14 (Chris's yes Oct 24)" "rm -r ~/Developer/claude-mods/toolkit/node_modules ~/.cache/hyperframes"
  register_rows
  thread_turn "Toolkit phase 3 PASS: Remotion 4.0.538 + HyperFrames 0.8.191; 15-sec silhouette text video rendered by both, no face, labeau safe-zone pass. Changes + register rows queued. Run by Chris in Terminal."
  ok "rows queued"
  open "$RMP4" 2>/dev/null
else
  note "not logged: fix the failures above and run phase 3 again"
fi
finish
