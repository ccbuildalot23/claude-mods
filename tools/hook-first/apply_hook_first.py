#!/usr/bin/env python3
"""apply_hook_first.py [LABEAU_OPS_DIR]: bake the hook-first opening into `labeau motion` (Oct 24, 2026).

Why: the Oct 23 Instagram insight on the DP-F8 "darkness" Reel showed a 70.2% skip rate in the first 3 s. Frame 1 was
an empty ground and his words arrived one line at a time from 0.5 s. Hook-first means:
  * the first stanza of his words (at most 2 lines; config motion.hook_lines) is fully on screen in frame 1
    (breath and bloom: the hook lines; kinetic: its first line), and later lines still arrive as before;
  * motion from frame 1: the words settle 14 px into place over 0-1.1 s while the nib and its bleed draw in;
  * reveal_check counts the hook: at 0.25 s the hook must already show, and nothing past it may.
Off switch: config motion.hook_first: false, or LABEAU_HOOK_FIRST=0 in the shell.

Edits two files, each only if every anchor is found exactly once (otherwise it changes nothing and says which anchor
is missing). Backups: <file>.bak-20261024-hookfirst. Running it twice is safe: a patched file is left alone.
"""
import os, shutil, sys

OPS = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Developer/labeau-ops")
SKIP = {".git", "node_modules", "vendor", "__pycache__", "backups", "data"}


def locate(ops=OPS):
    """labeau-ops keeps render_motion.py in its scripts folder and the stanza template under motion/templates; find each
    one on its own (exactly one of each, outside backups and vendored folders) instead of assuming where they sit."""
    py, tpl = [], []
    for root, dirs, files in os.walk(ops):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith((".", "_", "tmp"))]
        if "render_motion.py" in files:
            py.append(os.path.join(root, "render_motion.py"))
        if "index.html" in files and root.replace(os.sep, "/").endswith("templates/stanza"):
            tpl.append(os.path.join(root, "index.html"))
    if len(py) != 1 or len(tpl) != 1:
        raise SystemExit(f"NOT CHANGED: expected one render_motion.py and one templates/stanza/index.html under {ops}; "
                         f"found scripts {py or 'none'} and templates {tpl or 'none'}")
    return py[0], tpl[0]
TAG = "hook-first (Oct 24, 2026)"
BAK = ".bak-20261024-hookfirst"

PY_EDITS = [
    ("def fill(style, lines, ground, plate_name, t,",
     '''def hook_lines(style, lines, stanza_starts=()):
    """hook-first (Oct 24, 2026): how many of his lines are on screen in frame 1, and their share of the words' ink.
    The 70.2% first-3-second skip on DP-F8 came from an empty first frame. kinetic shows one line at a time, so its
    hook is its first line; breath and bloom show the first stanza, at most motion.hook_lines (default 2)."""
    mc = motion_cfg()
    if os.environ.get("LABEAU_HOOK_FIRST") == "0" or mc.get("hook_first") is False or not lines:
        return 0, 0.0
    first = min([int(i) for i in stanza_starts if 0 < int(i) < len(lines)] or [len(lines)])
    n = 1 if style == "kinetic" else max(1, min(first, int(mc.get("hook_lines", 2))))
    share = 1.0 if style == "kinetic" else sum(len(l) for l in lines[:n]) / max(sum(len(l) for l in lines), 1)
    return n, round(share, 3)

def fill(style, lines, ground, plate_name, t,'''),
    ("    body, kin = font_sizes(lines)\n",
     "    body, kin = font_sizes(lines)\n"
     "    t[\"hook_n\"], t[\"hook_share\"] = hook_lines(style, lines, stanza_starts)   # hook-first (Oct 24, 2026); reveal_check reads it\n"),
    ('            "{{STANZA_STARTS_JSON}}": json.dumps(',
     '            "{{HOOK_N}}": str(t["hook_n"]),   # hook-first (Oct 24, 2026): his lines on screen in frame 1\n'
     '            "{{STANZA_STARTS_JSON}}": json.dumps('),
    ('    return {"ok": final > 0 and early <= 0.25 * final, "early_px": early, "final_px": final}',
     '''    share = float(t.get("hook_share") or 0)   # hook-first (Oct 24, 2026): the hook is up from frame 1, and it must be
    if share >= 1.0:                           # kinetic: its first line is up; the final frame shows a different line
        ok = final > 0 and early > 0
    elif share > 0:
        ok = final > 0 and 0.5 * share * final <= early <= (share + 0.25 * (1 - share)) * final   # the hook, plus at most a quarter of the rest
    else:
        ok = final > 0 and early <= 0.25 * final
    return {"ok": ok, "early_px": early, "final_px": final, **({"hook_share": share} if share else {})}'''),
]

HTML_EDITS = [
    ("      const STANZA_STARTS = {{STANZA_STARTS_JSON}};",
     "      const HOOK = {{HOOK_N}};   // hook-first (Oct 24, 2026): this many of his lines are on screen in frame 1\n"
     "      const STANZA_STARTS = {{STANZA_STARTS_JSON}};"),
    ("        const tl = gsap.timeline({ paused: true });\n",
     "        const tl = gsap.timeline({ paused: true });\n"
     "        // hook-first (Oct 24, 2026): motion from frame 1, the words settle into place while the nib draws in\n"
     "        if (HOOK) tl.fromTo(block, { y: p.top - ANCHOR - 14 }, { y: p.top - ANCHOR, duration: 1.1, ease: \"power2.out\", immediateRender: false }, 0);\n"),
    ("""        document.querySelectorAll(".line").forEach((ln, i) => {
          tl.fromTo(ln.querySelectorAll(".w"),""",
     """        document.querySelectorAll(".line").forEach((ln, i) => {
          if (i < HOOK) { gsap.set(ln.querySelectorAll(".w"), { opacity: 1, y: 0, filter: "blur(0px)" }); return; }   // hook-first
          tl.fromTo(ln.querySelectorAll(".w"),"""),
    ("""          const chars = ln.querySelectorAll(".ch");
""",
     """          const chars = ln.querySelectorAll(".ch");
          if (i < HOOK) { gsap.set(chars, { opacity: 1, x: 0, filter: "blur(0px)" }); return; }   // hook-first
"""),
    ("""        document.querySelectorAll(".kline").forEach((k, i) => {
          tl.fromTo(k.querySelectorAll(".mask > span"), { yPercent: 115 },""",
     """        document.querySelectorAll(".kline").forEach((k, i) => {
          if (i === 0 && HOOK) gsap.set(k.querySelectorAll(".mask > span"), { yPercent: 0 });   // hook-first: up in frame 1
          else tl.fromTo(k.querySelectorAll(".mask > span"), { yPercent: 115 },"""),
]


def patch(path, edits):
    src = open(path, encoding="utf-8").read()
    if TAG in src:
        return "already patched"
    missing = [old.splitlines()[0].strip() for old, _ in edits if src.count(old) != 1]
    if missing:
        raise SystemExit(f"NOT CHANGED {path}: anchor not found exactly once: {missing}")
    for old, new in edits:
        src = src.replace(old, new, 1)
    shutil.copy2(path, path + BAK)
    open(path, "w", encoding="utf-8").write(src)
    return "patched"


if __name__ == "__main__":
    PY, HTML = locate()
    print("found", PY); print("found", HTML)
    for p in (PY, HTML):
        if not os.path.exists(p):
            raise SystemExit(f"missing {p}")
    # check both before touching either
    for p, e in ((PY, PY_EDITS), (HTML, HTML_EDITS)):
        s = open(p, encoding="utf-8").read()
        if TAG not in s:
            bad = [o.splitlines()[0].strip() for o, _ in e if s.count(o) != 1]
            if bad:
                raise SystemExit(f"NOT CHANGED (nothing edited): {os.path.basename(p)} is missing {bad}")
    print("render_motion.py:", patch(PY, PY_EDITS))
    print("stanza index.html:", patch(HTML, HTML_EDITS))
    print("HOOK-FIRST OK")
