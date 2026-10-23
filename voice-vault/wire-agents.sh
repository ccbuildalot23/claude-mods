#!/bin/bash
# One-time wiring for the diary-to-brand pathway: points labeau-ops sessions, Grok and
# Muse at the Hierophant Lens and cleared.csv. Safe to run twice (each step checks first).
set -euo pipefail
cd "$(dirname "$0")"
OPS="$HOME/Developer/labeau-ops"
BRIDGE="$HOME/Developer/grok-bridge"
export TZ=America/New_York
python3 - "$OPS" "$BRIDGE" <<'PY'
import datetime as dt, pathlib, re, sys
ops, bridge = map(pathlib.Path, sys.argv[1:3])
wiring = pathlib.Path("wiring")
now = dt.datetime.now()

claude = ops / "CLAUDE.md"
s = claude.read_text()
para = (wiring / "claude-md.md").read_text().strip()
if "Hierophant Lens and journal lines" not in s:
    anchor = "\n## Before and after any change"
    s = s.replace(anchor, "\n" + para + "\n" + anchor, 1) if anchor in s else s.rstrip("\n") + "\n\n" + para + "\n"
    claude.write_text(s)
    print("labeau-ops CLAUDE.md: Lens rule added")
else:
    print("labeau-ops CLAUDE.md: already has the Lens rule")

ign = ops / ".gitignore"
line = "data/share-candidates/share-candidates.csv"
g = ign.read_text() if ign.exists() else ""
if line not in g.splitlines():
    ign.write_text(g.rstrip("\n") + ("\n" if g else "") + line + "\n")
    print("labeau-ops .gitignore: full library kept out of git (cleared.csv can be committed)")

roles = {"grok": ("C2G", "Add to your standing instructions, and to every sub-agent that plans LaBeau or personal-brand work (Audience Scout, Storyteller and the rest): read the Lens before planning anything."),
         "muse": ("C2M", "Add to your standing instructions: read the Lens before planning any Meta work (Instagram, Facebook group, Threads), including captions, Reels and comments.")}
body = (wiring / "bridge-note.md").read_text()
sent = []
for agent, (prefix, role_line) in roles.items():
    box = bridge / f"to-{agent}"
    if any(p.name.endswith("hierophant-lens.md") for p in box.glob(f"{prefix}-*")):
        print(f"bridge: {agent} already has the Lens note")
        continue
    day = now.strftime("%Y-%m-%d")
    nums = [int(m.group(1)) for p in box.glob(f"{prefix}-{day}-*") if (m := re.match(rf"{prefix}-{day}-(\d+)", p.name))]
    mid = f"{prefix}-{day}-{max(nums, default=0) + 1:03d}"
    head = f"""---
id: {mid}
type: request
from: claude
to: {agent}
created_et: {now.strftime('%Y-%m-%d %H:%M')} ET
topic: other
thread: threads/labeau.md
reply_to:
status: new
needs_chris: no
chris_words: verbatim (Chris to Claude, Oct 23, 2026, 13:37 and 15:27 ET)
airtable: none
---
"""
    (box / f"{mid}-hierophant-lens.md").write_text(head + body.replace("ROLE_LINE", role_line))
    sent.append(mid)
    print(f"bridge: sent {mid} to {agent}")
if sent:
    with (bridge / "threads" / "labeau.md").open("a") as f:
        f.write(f"\n### {now.strftime('%Y-%m-%d %H:%M')} ET - Claude Code\n"
                "Diary-to-brand pathway v2 is live (claude-mods journal gate). Everything in Chris's journal is fair game; "
                "names are the one stop. New: labeau-ops/data/hierophant-lens/hierophant-lens.md (read before any planning) "
                "and labeau-ops/data/share-candidates/cleared.csv (lines he cleared on his Monday docket, quoted exactly). "
                f"labeau-ops CLAUDE.md points every session at them. Asked {' and '.join(sent)} to add the rule to standing instructions.\n")
    print("bridge: thread turn added to threads/labeau.md")
PY
