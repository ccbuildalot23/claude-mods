#!/bin/bash
# finish_on_mac.sh: run from the unpacked tools/hook-first folder, on the Mac, after 8:40 am (renders are refused overnight).
# 1) stages the hook-first DP-F8 Reel (two-row split, his yes Oct 24, 2026) for IG and TikTok
# 2) patches labeau-ops for hook-first openings and runs the unit checks
# 3) test-renders DP-F8 through the patched `labeau motion` and prints where the frames are
HERE="$(cd "$(dirname "$0")" && pwd)"
OPS="${LABEAU_OPS:-$HOME/Developer/labeau-ops}"
POSTS="${LABEAU_POSTS:-$HOME/LaBeau-Assets/04-posts}"
SLUG=dp-f8-hook-first-2026-10-24
R=""
mkdir -p "$POSTS/reels" || exit 1
cp "$HERE/dp-f8-hook-first__9x16.mp4" "$POSTS/reels/${SLUG}__ig_9x16.mp4" && cp "$HERE/dp-f8-hook-first__9x16.mp4" "$POSTS/reels/${SLUG}__tt_9x16.mp4" && R="$R staged=OK" || R="$R staged=FAIL"
python3 "$HERE/apply_hook_first.py" "$OPS" && R="$R patch=OK" || { echo "=== SUMMARY"; echo "$R patch=FAIL (nothing in labeau-ops was changed)"; exit 1; }
python3 "$HERE/test_hook_first.py" "$OPS" 2>&1 | tail -3
python3 "$HERE/test_hook_first.py" "$OPS" >/dev/null 2>&1 && R="$R tests=OK" || R="$R tests=FAIL"
if [ "${SKIP_RENDER:-0}" = "1" ]; then R="$R render=SKIPPED"; else
  OUT=$(cd "$OPS" && bin/labeau motion DP-F8 --style breath --no-ready 2>&1)
  echo "$OUT" | tail -25
  echo "$OUT" | grep -q '"status": "BUILT"' && R="$R render=BUILT" || R="$R render=NOT-BUILT"
  ls -td "$HOME/LaBeau-Assets/03-review/previews/motion/DP-F8-"* 2>/dev/null | head -1
fi
echo "=== SUMMARY"
echo "$R"
