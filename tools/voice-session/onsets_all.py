import os, sys, json, hashlib
from multiprocessing import Pool
OPS = "/tmp/claude-0/ops"
os.environ["LABEAU_ASSETS"] = "/tmp/claude-0/assets"
os.environ["LABEAU_VOICE_OCR"] = "tesseract"
sys.path.insert(0, OPS + "/scripts")
import voice_session as V
plan = V.load_plan()
cache = V.load_onsets()
jobs, seen = [], set()
for s in plan["slots"]:
    if s["voice"] not in ("new", "ab-test"): continue
    texts = [t for _, _, t in V.slot_lines(plan, s)]
    for f in V.slot_files(s):
        key = f"{V.file_key(f)}|{hashlib.sha1(' / '.join(texts).encode()).hexdigest()[:10]}"
        if key not in cache and key not in seen: jobs.append((key, f, texts)); seen.add(key)
def work(j):
    key, f, texts = j
    return key, dict(V.scan_onsets(f, texts), file=os.path.basename(f))
print(len(jobs), "files", flush=True)
with Pool(4) as p:
    for n, (k, v) in enumerate(p.imap_unordered(work, jobs)):
        cache[k] = v
        json.dump(cache, open(V.ONSETS, "w"), indent=1)
        print(n + 1, v["file"], v["onsets"], v["duration"], flush=True)
print("DONE", flush=True)
