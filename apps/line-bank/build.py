#!/usr/bin/env python3
"""Line-bank librarian: builds a searchable shelf of Chris's own lines.

Reads labeau-ops data/fragments.csv (his approved lines), pieces.csv (poem titles) and placements.csv
(how often each line went out), plus the cento files in the vault's Packets folder (which lines a cento
used). It only reads and counts. It never writes, edits or orders a line: the pen rule.
Output: ~/Developer/claude-mods/apps-out/line-bank.html (local only, never committed).
"""
import collections, glob, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

# Image tags: a word in the line puts it on that shelf. Counting, not reading meaning.
IMAGES = {
    "water": r"\b(water|wave|waves|ocean|sea|rain|river|tide|tears?|swim|surf\w*|drown\w*)\b",
    "sun and light": r"\b(sun|sunrise|sunset|light|shine|glow|dawn|morning|horizon)\b",
    "night": r"\b(night|moon|stars?|dark|midnight|evening)\b",
    "flowers": r"\b(rose|roses|stem|stems|petal\w*|bloom\w*|flower\w*|garden)\b",
    "fire and heat": r"\b(fire|flame|burn\w*|heat|warm\w*|degrees)\b",
    "road and travel": r"\b(road|path|drive|miles?|journey|wander\w*|home|door)\b",
    "time": r"\b(time|clock|years?|days?|seasons?|forever|again)\b",
    "faith": r"\b(god|grace|heaven|pray\w*|faith\w*|bless\w*|angel\w*)\b",
    "body and heart": r"\b(heart|hands?|eyes|skin|breath\w*|bleed\w*|blood|lips?)\b",
    "music": r"\b(song|sing\w*|melody|rhythm|beat|cadence|music)\b",
}


def norm(s):
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9' ]+", " ", s.lower()).split()


def main():
    frags = common.read_csv("fragments.csv")
    if not frags:
        sys.exit(f"No fragments.csv under {common.OPS}/data. Set LABEAU_OPS if labeau-ops lives elsewhere.")
    titles = {p["piece_id"]: p["title"] for p in common.read_csv("pieces.csv")}
    posted, planned = collections.Counter(), collections.Counter()
    for p in common.read_csv("placements.csv"):
        fid = p.get("fragment_id", "")
        if not fid:
            continue
        if p.get("state") == "posted":
            posted[fid] += 1
        elif p.get("state") in ("planned", "held", "released"):
            planned[fid] += 1

    vault = common.ops_config("vault")
    packets = os.path.join(vault, common.ops_config("packets_folder") or "Recovery/LaBeau Catalog/Packets")
    centos = []
    for path in sorted(glob.glob(os.path.join(packets, "*Cento*.md"))):
        name = os.path.basename(path)
        m = re.search(r"Cento (\w+) - (.+?) - (\d{4}-\d{2}-\d{2})", name)
        label = f"Cento {m.group(1)} ({m.group(3)})" if m else name
        text = " ".join(norm(open(path, encoding="utf-8").read()))
        centos.append((label, f" {text} "))

    rows = []
    for f in frags:
        lines = [l.strip() for l in f["text"].split(" / ") if l.strip()]
        used_in = []
        for label, text in centos:
            if any(len(norm(l)) >= 3 and f" {' '.join(norm(l))} " in text for l in lines):
                used_in.append(label)
        low = f["text"].lower()
        rows.append({
            "id": f["fragment_id"],
            "poem": titles.get(f["piece_id"], f["piece_id"]),
            "lines": lines,
            "theme": (f.get("subject") or f.get("subject_proposed") or "untagged").replace("_", " "),
            "images": [k for k, rx in IMAGES.items() if re.search(rx, low)],
            "approved": f.get("approved_by") == "Chris",
            "date": f.get("approved_on", ""),
            "posted": posted[f["fragment_id"]],
            "planned": planned[f["fragment_id"]],
            "centos": used_in,
        })
    path = common.write_page("line-bank", {"rows": rows, "centoCount": len(centos)})
    print(f"Line bank: {len(rows)} lines, {len(centos)} cento files read. Open {path}")


if __name__ == "__main__":
    main()
