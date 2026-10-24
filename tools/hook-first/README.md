# hook-first

Puts his hook on screen in frame 1 of every `labeau motion` Reel. Built Oct 24, 2026, after Instagram reported a 70.2% skip rate in the first 3 seconds of the DP-F8 "darkness" Reel.

- `apply_hook_first.py [~/Developer/labeau-ops]`: patches `render_motion.py` and `motion/templates/stanza/index.html`.
  - breath and bloom: the first stanza (at most 2 lines) is on screen in frame 1.
  - kinetic: the first line is up in frame 1.
  - Motion starts at frame 1.
  - `reveal_check` requires the hook at 0.25 s.
  - If any anchor is missing, nothing is changed. A file that is already patched is skipped.
  - Backups are saved as `*.bak-20261024-hookfirst`.
- `test_hook_first.py [~/Developer/labeau-ops]`: unit checks for the patch.
- `finish_on_mac.sh`: run on the Mac after 8:40 am. Stages the hook-first DP-F8 Reel in 04-posts/reels, applies the patch, runs the checks, and test-renders DP-F8.
- `dp-f8-hook-first__9x16.mp4`: the rebuilt DP-F8 Reel. Each line takes two rows in Gloock 74 px (his yes, Oct 24, 2026).
- `hook_first_reel.py SPEC.json OUT.mp4`: a standalone Gloock hook-first Reel renderer (PIL + ffmpeg). It checks the safe zone and contrast on every frame. This is how the DP-F8 rebuild was made.

To turn it off, set `motion.hook_first: false` in the labeau-ops config, or `LABEAU_HOOK_FIRST=0` in the shell.
