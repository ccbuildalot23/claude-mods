#!/bin/bash
# One-time wiring for the Strategy Lens (Chris's standing rule, Oct 24, 2026): puts it beside
# the Hierophant Lens in labeau-ops CLAUDE.md and the global CLAUDE.md, copies the full text
# into labeau-ops, and asks Grok and Muse to add it. Safe to run twice (each step checks first).
set -euo pipefail
cd "$(dirname "$0")"
OPS="${OPS:-$HOME/Developer/labeau-ops}"
BRIDGE="${BRIDGE:-$HOME/Developer/grok-bridge}"
GLOBAL="${GLOBAL:-$HOME/.claude/CLAUDE.md}"
export TZ=America/New_York
python3 - "$OPS" "$BRIDGE" "$GLOBAL" <<'PY'
import datetime as dt, pathlib, re, shutil, sys
ops, bridge, glob_md = map(pathlib.Path, sys.argv[1:4])
wiring, templates = pathlib.Path("wiring"), pathlib.Path("templates")
now = dt.datetime.now()
MARK = "**Strategy Lens (Oct 24, 2026"
para = (wiring / "claude-md-strategy.md").read_text().strip()

lens = ops / "data" / "strategy-lens" / "strategy-lens.md"
if not lens.exists():
    lens.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(templates / "strategy-lens.md", lens)
    print("labeau-ops: data/strategy-lens/strategy-lens.md written")
else:
    print("labeau-ops: strategy-lens.md already there (left as is)")

claude = ops / "CLAUDE.md"
s = claude.read_text()
if MARK not in s:
    m = re.search(r"^\*\*Hierophant Lens and journal lines.*$", s, re.M)
    if m:
        s = s[:m.end()] + "\n\n" + para + s[m.end():]
    elif "\n## Before and after any change" in s:
        s = s.replace("\n## Before and after any change", "\n" + para + "\n\n## Before and after any change", 1)
    else:
        s = s.rstrip("\n") + "\n\n" + para + "\n"
    claude.write_text(s)
    print("labeau-ops CLAUDE.md: Strategy Lens added beside the Hierophant Lens")
else:
    print("labeau-ops CLAUDE.md: already has the Strategy Lens")

if glob_md.exists():
    g = glob_md.read_text()
    if MARK not in g:
        shutil.copy(glob_md, glob_md.with_name(f"CLAUDE.md.bak-{now:%Y%m%d}-strategy"))
        gpara = (para.replace("full text `data/strategy-lens/strategy-lens.md`",
                              "full text `~/Developer/labeau-ops/data/strategy-lens/strategy-lens.md`")
                     .replace("the Hierophant Lens above",
                              "the Hierophant Lens (`~/Developer/labeau-ops/data/hierophant-lens/hierophant-lens.md`)"))
        glob_md.write_text(g.rstrip("\n") + "\n\n" + gpara + "\n")
        print(f"{glob_md}: Strategy Lens added (backup beside it)")
    else:
        print(f"{glob_md}: already has the Strategy Lens")
else:
    print(f"{glob_md}: not found, skipped")

roles = {"grok": ("C2G", "Claude Code's side is wired: labeau-ops CLAUDE.md, the global CLAUDE.md and labeau-ops/data/strategy-lens/. Thanks for research/strategy-lens.md and the ChatGPT, Perplexity and Hermes notes. Please add it to your own standing instructions and to every sub-agent that plans (Audience Scout, Storyteller, Bridge Keeper and the rest), and have Bridge Keeper follow up their acks."),
         "muse": ("C2M", "Add it to your standing instructions next to the Hierophant Lens, and use it whenever you plan Meta work (Instagram, Facebook group, Threads).")}
body = (wiring / "bridge-note-strategy.md").read_text()
sent = []
for agent, (prefix, role_line) in roles.items():
    box = bridge / f"to-{agent}"
    if any(p.name.endswith("strategy-lens.md") for p in box.glob(f"{prefix}-*")):
        print(f"bridge: {agent} already has the Strategy Lens note")
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
chris_words: verbatim (Chris to Claude, Oct 24, 2026, 02:58 ET): "Standing rule: STRATEGY LENS (from Chris, Oct 24 2026). Add to CLAUDE.md and standing rules." and "I've given a yes to all of these items"
airtable: none
---
"""
    (box / f"{mid}-strategy-lens.md").write_text(head + body.replace("ROLE_LINE", role_line) + "\n## Status log\n")
    sent.append(mid)
    print(f"bridge: sent {mid} to {agent}")
if sent:
    with (bridge / "threads" / "labeau.md").open("a") as f:
        f.write(f"\n### {now.strftime('%Y-%m-%d %H:%M')} ET - Claude Code\n"
                "Strategy Lens wired on the Claude side (Chris's standing rule, Oct 24). It sits beside the Hierophant Lens in "
                "labeau-ops CLAUDE.md and the global CLAUDE.md; full text at labeau-ops/data/strategy-lens/strategy-lens.md "
                "(same words as research/strategy-lens.md). Every plan opens with \"Lens: [framework]. Answers: ... . "
                f"Decision: one yes/no for Chris.\" Asked {' and '.join(sent)} to add it to standing instructions; "
                "Grok already briefed ChatGPT, Perplexity and Hermes.\n")
    print("bridge: thread turn added to threads/labeau.md")
PY
