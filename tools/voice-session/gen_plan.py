"""Build data/voice/session-2026-10-25.json from placements, plan_3x and fragments (run once, Oct 24, 2026)."""
import csv, json, os, re, sys

OPS = sys.argv[1]
ASSETS = sys.argv[2]
OUT = sys.argv[3]
FROM, TO = "2026-10-26", "2026-11-24"

fr = {r["fragment_id"]: r for r in csv.DictReader(open(f"{OPS}/data/fragments.csv", encoding="utf-8"))}
pieces = {r["piece_id"]: r for r in csv.DictReader(open(f"{OPS}/data/pieces.csv", encoding="utf-8"))}
px = {r["plan_id"]: r for r in csv.DictReader(open(f"{OPS}/data/plan_3x.csv", encoding="utf-8"))}
pl = list(csv.DictReader(open(f"{OPS}/data/placements.csv", encoding="utf-8")))

def lines(t):
    return [re.sub(r"\s+", " ", l).strip() for l in t.split(" / ") if l.strip()]

def key(l):
    return re.sub(r"[^a-z0-9]", "", l.lower().replace("\u2019", "'"))

ALREADY = {"P4359": "his Red Stems read-aloud (original audio)", "P4446": "his Wavy read-aloud",
           "P4486": "his 70 Any Degrees read-aloud", "P4564": "his Red Stems read-aloud", "P4606": "his Wavy read-aloud"}
SILENT = {
    "P4365": "cut to the beat of his song by the Reel Director; a voice would fight the edit",
    "P4363": "cut to the beat of his song by the Reel Director; a voice would fight the edit",
    "P4357": "photo carousel; Instagram can't carry a voice track on stills",
    "P4361": "highlight of earlier Wavy lines; kept as it is",
    "P4464": "spoken intro (SPKF-F1), not poem lines",
    "P4608": "spoken intro (SPKF-F1), not poem lines",
    "P4502": "highlight built around a spoken piece (SPKC-F1)",
    "P4510": "highlight built around a spoken notice (SPKN-F1)",
    "P4556": "spoken piece (SPKW-F1), not poem lines",
    "P4418": "control pair A: tables gem silent Oct 26, voiced Nov 13",
    "P4618": "control pair B: view gem voiced Oct 29, silent Nov 24",
    "P4444": "control pair C: training gem silent Nov 1, voiced Nov 19",
    "P4600": "control pair D: important gem voiced Nov 3, silent Nov 21",
}

def plan_row(r):
    m = re.search(r"(PX-\d{4}-\d\d-\d\d-\d)", r["notes"])
    return px.get(m.group(1)) if m else (px.get(r["asset_slug"].upper()) if r["asset_slug"].startswith("px-") else None)

def files_for(slug):
    out = []
    for f in (f"04-posts/reels/{slug}__ig_9x16.mp4", f"04-posts/reels/{slug}__ig_4x5.mp4", f"04-posts/reels/{slug}__tt_9x16.mp4"):
        if os.path.exists(os.path.join(ASSETS, f)):
            out.append(f)
    return out

slots = []
for r in pl:
    if not (FROM <= r["date"] <= TO and r["platform"] == "instagram" and r["state"] == "planned"):
        continue
    p = plan_row(r)
    slug = (p["plan_id"].lower() if p else r["asset_slug"])
    units = p["unit_ids"].split() if p else ([r["fragment_id"]] if r["fragment_id"] else [])
    twin = [t["placement_id"] for t in pl if t["platform"] == "tiktok" and t["date"] == r["date"]
            and t["state"] == "planned" and (t["asset_slug"] == r["asset_slug"]) and (plan_row(t) == p)]
    voice = "already" if r["placement_id"] in ALREADY else "silent" if r["placement_id"] in SILENT else "new"
    why = ALREADY.get(r["placement_id"]) or SILENT.get(r["placement_id"]) or ""
    if slug == "inl-f4-no-more-victim-me":
        files = ["04-posts/motion/inl-f4-no-more-victim-me__breath.mp4"]
    else:
        files = files_for(slug)
    slots.append({"placement": r["placement_id"], "tiktok": twin, "date": r["date"],
                  "time": (p or {}).get("time_ig", "") or re.search(r"(\d\d:\d\d)", r["notes"]).group(1),
                  "format": (p or {}).get("format", ""), "slug": slug,
                  "fragments": units if voice == "new" else units, "voice": voice, "why": why, "files": files})

# the DP-F8 A/B (thread "Cut first-3-second Reel skips"): his read laid on the hook-first build, kept in 03-review
slots.append({"placement": "DP-F8-B", "tiktok": [], "date": "A/B", "time": "", "format": "hook-first reel",
              "slug": "dp-f8-hook-first-2026-10-24", "fragments": ["DP-F8"], "voice": "ab-test",
              "why": "B side of the DP-F8 voice A/B", "files": files_for("dp-f8-hook-first-2026-10-24")})

need = []
for s in slots:
    if s["voice"] in ("new", "ab-test"):
        for u in s["fragments"]:
            if u not in need:
                need.append(u)

# chain fragments of one piece that overlap (a suffix of one is the prefix of the next) into one passage
chains = []
for fid in need:
    chains.append({"piece": fr[fid]["piece_id"], "lines": lines(fr[fid]["text"]), "frags": [fid]})
changed = True
while changed:
    changed = False
    for a in chains:
        for b in chains:
            if a is b or a["piece"] != b["piece"]:
                continue
            ka, kb = [key(x) for x in a["lines"]], [key(x) for x in b["lines"]]
            # b inside a
            for i in range(len(ka) - len(kb) + 1):
                if ka[i:i + len(kb)] == kb:
                    a["frags"] += b["frags"]; chains.remove(b); changed = True; break
            if changed: break
            for k in range(min(len(ka), len(kb)) - 1, 0, -1):
                if ka[-k:] == kb[:k]:
                    a["lines"] += b["lines"][k:]; a["frags"] += b["frags"]; chains.remove(b); changed = True; break
            if changed: break
        if changed: break

SETS = {  # by feeling, so he stays in one mood per memo
    1: ["DP", "C3", "C1", "W5", "GF"],
    2: ["VOH", "INL", "PP", "PR", "DP-E", "TM"],
    3: ["MU", "NBH", "NF", "SM", "SP", "TF", "TIME", "PH"],
}
GEM_SET = {
    1: ["GEM-felt", "GEM-tables-round-where", "GEM-build-tables-people-around", "GEM-roses", "GEM-another-day-another",
        "L21", "GEM-can-enjoy-life", "GEM-grapes", "GEM-time-precious-cherish"],
    2: ["GEM-biggest-fear-knowing", "GEM-broke-my-own-heart", "GEM-brain-wrapped-own", "GEM-blessing-the-reckoning",
        "GEM-cause-couldnt-because", "GEM-phonetically", "GEM-bleed-you-whats-real", "GEM-shadow"],
}

def set_of(c):
    f = c["frags"][0]
    if c["piece"] == "GEM":
        for n, ids in GEM_SET.items():
            if f in ids:
                return n
        return 3
    if f.startswith("DP-E"):
        return 2
    for n, ps in SETS.items():
        if c["piece"] in ps:
            return n
    return 3

ORDER = {p: i for n in SETS for i, p in enumerate(SETS[n])}
chains.sort(key=lambda c: (set_of(c), 0 if c["frags"] == ["DP-F8"] else 1, c["piece"] == "GEM", ORDER.get(c["piece"], 99),
                           min(need.index(f) for f in c["frags"])))
passages, count = [], {}
for c in chains:
    n = set_of(c); count[n] = count.get(n, 0) + 1
    title = pieces.get(c["piece"], {}).get("title", "") if c["piece"] != "GEM" else "a gem"
    frags = {}
    kl = [key(x) for x in c["lines"]]
    for f in c["frags"]:
        kf = [key(x) for x in lines(fr[f]["text"])]
        i = next(i for i in range(len(kl) - len(kf) + 1) if kl[i:i + len(kf)] == kf)
        frags[f] = [i, i + len(kf) - 1]
    passages.append({"id": f"S{n}-{count[n]:02d}", "set": n, "piece": c["piece"], "title": title,
                     "lines": c["lines"], "fragments": frags})

plan = {"session": "2026-10-25", "window": [FROM, TO],
        "built_by": "voice thread, Oct 24, 2026 (his ask: his voice on about 85% of next month's Reels and TikToks)",
        "passages": passages, "slots": slots}
json.dump(plan, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
ig = [s for s in slots if s["voice"] != "ab-test"]
v = sum(s["voice"] in ("new", "already") for s in ig)
print(len(ig), "slots", v, "voiced", f"{v/len(ig):.1%}", len(passages), "passages",
      sum(len(" ".join(p["lines"]).split()) for p in passages), "words")
for p in passages:
    print(p["id"], p["piece"], p["title"], list(p["fragments"]), len(p["lines"]))
print("built:", sum(1 for s in slots if s["voice"] in ("new", "ab-test") and s["files"]))
print("twins missing:", [s["placement"] for s in slots if not s["tiktok"] and s["voice"] != "ab-test"])
