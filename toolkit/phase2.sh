#!/bin/bash
# Phase 2: ffmpeg, Node.js LTS, Python 3 (Homebrew, pinned) and Puppeteer 25.16.0 (npm, package-lock).
# Test: render one 4-slide carousel from Chris's own text, checked for the safe zone, Gloock, contrast and verbatim words.
#   ./phase2.sh                 uses text/sample-darkness.txt (his posted lines from the Oct 22 darkness Reel)
#   ./phase2.sh my-lines.txt    any text file of his: one slide per paragraph, blank line between
PHASE=2
. "$(dirname "$0")/bin/lib.sh"
TEXT="${1:-$TK/text/sample-darkness.txt}"
echo "Toolkit phase 2 (ffmpeg, Node, Python, Puppeteer), $(date '+%Y-%m-%d %H:%M ET')"

step "Homebrew"
ensure_brew || { finish; exit 1; }
step "ffmpeg (16)"
ensure_formula ffmpeg
step "Node.js LTS (41)"
ensure_node
step "Python 3 (33)"
ensure_python

step "Puppeteer $(node -p 'require(process.argv[1]).dependencies.puppeteer' "$TK/package.json") (29), with Remotion, HyperFrames and GSAP locked for phase 3"
(cd "$TK" && npm ci --no-audit --no-fund --loglevel=error --no-update-notifier) && ok "npm ci from package-lock.json" || bad "npm ci failed"
PV="$(node -p 'require(process.argv[1]).version' "$TK/node_modules/puppeteer/package.json" 2>/dev/null)"
[ "$PV" = "25.16.0" ] && ok "works: puppeteer $PV" || bad "puppeteer is $PV, not 25.16.0"
[ -x "$(cd "$TK" && node bin/browser-path.mjs)" ] && ok "works: Puppeteer's pinned chrome-headless-shell is installed" || bad "chrome-headless-shell missing (re-run: cd $TK && npx puppeteer browsers install chrome-headless-shell)"

step "Test: 4-slide carousel from Chris's text ($(basename "$TEXT"))"
OUTD="$TK/out/carousel-test-$(date +%Y%m%d-%H%M)"
if (cd "$TK" && node carousel/render.mjs "$TEXT" "$OUTD" smoke) | sed 's/^/    /'; [ "${PIPESTATUS[0]}" -eq 0 ]; then
  N="$(ls "$OUTD"/slide-*.png 2>/dev/null | wc -l | tr -d ' ')"
  [ "$N" = 4 ] && ok "works: 4 slides rendered in $OUTD" || bad "expected 4 slides, got $N (the file needs 4 paragraphs)"
else
  bad "carousel render failed"
fi
if [ -f "$OUTD/slide-1.png" ]; then
  SIZE="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$OUTD/slide-1.png" | head -1 | cut -d, -f1,2)"
  [ "$SIZE" = "1080,1350" ] && ok "slides are 1080x1350 (4:5, shown whole in the IG/TikTok/Gist feed)" || bad "slide size is $SIZE"
  ffmpeg -y -loglevel error -framerate 1/3 -i "$OUTD/slide-%d.png" -vf "scale=1080:1350,format=yuv420p" -r 30 "$OUTD/carousel-preview.mp4" && ok "works: ffmpeg made a 12-second preview video from the slides" || bad "ffmpeg could not make the preview"
  [ -x "$OPS/bin/labeau" ] && "$OPS/bin/labeau" safe-zone "$OUTD" 2>&1 | tail -1 | sed 's/^/    labeau check: /'
fi

step "Blocked stays blocked"
grep -q '"node_modules/puppeteer"' "$TK/package-lock.json" && ok "versions locked in package-lock.json (npm ci installs only these)" || bad "package-lock.json missing puppeteer"
for f in ffmpeg; do
  [ "$TEST_BOX" = 1 ] || { brew list --pinned | grep -qx "$f" && ok "$f pinned against brew upgrade" || bad "$f not pinned"; }
done
CHECK="$(mktemp)"; printf 'one\n\ntwo\n' > "$CHECK"
(cd "$TK" && node carousel/render.mjs "$CHECK" "$(mktemp -d)" no-such-family >/dev/null 2>&1) && bad "carousel accepted an unknown color family" || ok "carousel refuses anything outside the brand families"

step "Removes cleanly"
(cd "$TK" && npm uninstall --dry-run puppeteer >/dev/null 2>&1) && ok "npm uninstall dry run passes (undo: rm -r toolkit/node_modules ~/.cache/puppeteer)" || bad "npm uninstall dry run failed"
[ "$TEST_BOX" = 1 ] || { brew uninstall --dry-run ffmpeg >/dev/null 2>&1 && ok "brew uninstall --dry-run ffmpeg passes" || note "brew uninstall dry run not available; undo is: brew unpin ffmpeg && brew uninstall ffmpeg"; }

step "Log: Changes rows, register rows, thread turn"
if [ "$FAILS" -eq 0 ]; then
  VERS="ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}'), node $(node -v), $("$PY" --version 2>&1)"
  change_row "Mac runtimes" "Homebrew $VERS, held with brew pin" "42 add-ons plan items 16, 41, 33 (Chris's yes Oct 24)" "brew unpin <name> && brew uninstall <name>"
  change_row "Media toolkit" "Puppeteer 25.16.0 (+ Remotion 4.0.538, HyperFrames 0.8.191, GSAP 3.15.0 locked, unused until phase 3) in claude-mods/toolkit; carousel test passed" "42 add-ons plan item 29" "rm -r ~/Developer/claude-mods/toolkit/node_modules ~/.cache/puppeteer"
  register_rows
  thread_turn "Toolkit phase 2 PASS: $VERS, Puppeteer 25.16.0; 4-slide carousel test rendered from Chris's own lines ($OUTD). Changes + register rows queued. Run by Chris in Terminal."
  ok "rows queued"
  open "$OUTD" 2>/dev/null
else
  note "not logged: fix the failures above and run phase 2 again"
fi
finish
