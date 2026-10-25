#!/usr/bin/env python3
"""His voice on his Reels: one recording session, cut into lines, laid onto the staged videos (Oct 24, 2026).

    voice_session.py check                      the session plan: what gets his voice, what stays silent, and why
    voice_session.py onsets [--only PID]        when each of his lines appears on screen in each staged video (cached)
    voice_session.py cut <memo.m4a> [...]       find every passage in his memo(s), cut each line, report what's missing
    voice_session.py lay [--only PID]           put the line clips onto the videos, timed to the words on screen
    voice_session.py stage                      swap the voiced files into 04-posts (originals kept in _pre-voice-<date>)
    voice_session.py selftest                   the whole chain on this Mac with a synthetic read (say), nothing staged

His words, Oct 24, 2026: "I want to begin incorporating my voice in my videos going forward ... not every post, but we
can do 85% of the posts lets see how they do ... one long read and you can cut the audio, or a few short reads, and
then apply it directly to the videos".

Rules this keeps, in code:
  - His words only. The script is the posts' own on-screen lines from data/fragments.csv, word for word; a passage is
    refused at lay time when fragments.csv no longer says what he recorded (a reworked gem gets a new read).
  - The picture is untouched. The video stream is copied bit for bit (checked by md5), so safe zones and hook-first
    frames stay exactly as approved. When his read runs longer than the video, the last frame is held, never cut.
  - A line is never heard before it is on screen. Each line clip starts when that line appears (read off the frames by
    OCR: Apple Vision on this Mac, tesseract elsewhere); the first line starts inside the first second.
  - Raw audio never leaves this Mac (whisper-cli, small.en). Output goes to 03-review first; `stage` is his hand.
  - Gist gets no voice (Gist posts are not in this plan, and nothing here writes to a Gist folder).
"""
import argparse
import array
import csv
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))

SESSION = os.environ.get("LABEAU_VOICE_SESSION", "2026-10-25")
PLAN = os.path.join(HERE, "data", "voice", f"session-{SESSION}.json")
ONSETS = os.path.join(HERE, "data", "voice", "onsets.json")
ASSETS = os.environ.get("LABEAU_ASSETS", os.path.expanduser("~/LaBeau-Assets"))
MODEL = os.path.expanduser("~/.whisper-models/ggml-small.en.bin")
SR = 48000                      # clip and mix rate
AN = 16000                      # analysis rate (whisper, energy)
FPS_SCAN = 3                    # frames per second read for line onsets
LUFS, TP, LRA = -14.0, -1.5, 11.0
GAP_S = 0.12                    # least air between two placed lines
MAX_HOLD_S = 12.0               # the most we will hold the last frame for a long read
TAKE_FLOOR = 0.60               # a take must contain this share of a passage's words
TAKE_TIE = 0.05                 # takes within this of the best count as equally good; the last one wins


def work_dir():
    return os.environ.get("LABEAU_VOICE_WORK") or os.path.join(ASSETS, "03-review", "voice", SESSION)


def tool(name):
    return shutil.which(name) or (f"/opt/homebrew/bin/{name}" if os.path.exists(f"/opt/homebrew/bin/{name}") else name)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------- words

def norm(w):
    return re.sub(r"[^a-z0-9%]", "", w.lower().replace("’", "'").replace("'", ""))


def words(text):
    """Words as spoken: hyphens, dashes and ellipses split; punctuation drops."""
    text = text.replace("…", " ").replace("...", " ")
    return [n for n in (norm(w) for w in re.split(r"[\s\-–—/]+", text)) if n]


def frag_lines(text):
    return [re.sub(r"\s+", " ", l).strip() for l in text.split(" / ") if l.strip()]


def fragments_csv():
    return {r["fragment_id"]: r for r in csv.DictReader(open(os.path.join(HERE, "data", "fragments.csv"), encoding="utf-8"))}


def load_plan(path=None):
    return json.load(open(path or PLAN, encoding="utf-8"))


def passage_of(plan, fid):
    for p in plan["passages"]:
        if fid in p["fragments"]:
            return p
    return None


def slot_lines(plan, slot):
    """[(passage_id, line_index, text)] for every line the slot's video shows, in order."""
    out = []
    for fid in slot["fragments"]:
        p = passage_of(plan, fid)
        a, b = p["fragments"][fid]
        out += [(p["id"], i, p["lines"][i]) for i in range(a, b + 1)]
    return out


def stale_fragments(plan, frs=None):
    """Fragments whose text in fragments.csv no longer matches what the script asked him to read."""
    frs = frs or fragments_csv()
    bad = {}
    for p in plan["passages"]:
        for fid, (a, b) in p["fragments"].items():
            if fid not in frs:
                bad[fid] = "not in fragments.csv"
            elif words(" ".join(frag_lines(frs[fid]["text"]))) != words(" ".join(p["lines"][a:b + 1])):
                bad[fid] = "words changed since the script"
    return bad


# ---------------------------------------------------------------- audio io

def decode(path, rate, out_wav, filters=None):
    cmd = [tool("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", path, "-vn"]
    if filters:
        cmd += ["-af", filters]
    run(cmd + ["-ar", str(rate), "-ac", "1", "-c:a", "pcm_s16le", out_wav])
    return out_wav


def read_pcm(wav):
    import wave
    with wave.open(wav, "rb") as w:
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
        return a, w.getframerate()


def write_pcm(wav, samples, rate):
    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(samples.tobytes())


def energy_db(samples, rate, hop=0.01):
    n = int(rate * hop)
    out = []
    for i in range(0, len(samples) - n + 1, n):
        seg = samples[i:i + n]
        s = sum(x * x for x in seg) / n
        out.append(10 * math.log10(s + 1.0) - 90.3)   # dBFS for s16
    return out


def silences(db, hop=0.01, min_len=0.12):
    """[(start_s, end_s)] runs quieter than the room plus 10 dB, at least min_len long."""
    if not db:
        return []
    floor = sorted(db)[max(0, len(db) // 10)]
    thr = max(floor + 10.0, -60.0)
    out, start = [], None
    for i, v in enumerate(db + [999]):
        if v < thr and start is None:
            start = i
        elif v >= thr and start is not None:
            if (i - start) * hop >= min_len:
                out.append((start * hop, i * hop))
            start = None
    return out


def quietest(db, t0, t1, hop=0.01):
    i0, i1 = max(0, int(t0 / hop)), min(len(db) - 1, int(t1 / hop))
    if i1 <= i0:
        return (t0 + t1) / 2
    k = min(range(i0, i1 + 1), key=lambda i: db[i])
    return k * hop


# ---------------------------------------------------------------- transcription

def whisper(wav16, tmp):
    """[(word, start_s, end_s)] heard, one entry per word (whisper-cli -ml 1 -sow, as audio_readback uses it)."""
    run([tool("whisper-cli"), "-m", MODEL, "-f", wav16, "-ml", "1", "-sow", "-oj", "-of", os.path.join(tmp, "t"), "-np"])
    return parse_whisper(json.load(open(os.path.join(tmp, "t.json"), encoding="utf-8")))


def parse_whisper(doc):
    out = []
    for s in doc.get("transcription", []):
        ws = words(s.get("text", ""))
        if not ws:
            continue
        a, b = s["offsets"]["from"] / 1000, s["offsets"]["to"] / 1000
        step = (b - a) / len(ws)
        for k, w in enumerate(ws):
            out.append((w, a + k * step, a + (k + 1) * step))
    return out


TRANSCRIBE = whisper   # tests swap this


# ---------------------------------------------------------------- finding passages in a memo

def similar(a, b):
    return a == b or (len(a) > 3 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.75)


def takes_of(pwords, heard):
    """Every place in `heard` that reads the passage: [(score, start_idx, end_idx, mapping)], mapping his word index to
    a heard index. A take must open on one of his first three words and contain TAKE_FLOOR of them, in order."""
    m = len(pwords)
    hw = [h[0] for h in heard]
    out, seen = [], set()
    for s in range(len(hw)):
        k0 = next((k for k in range(min(3, m)) if similar(hw[s], pwords[k])), None)
        if k0 is None:
            continue
        win = hw[s:s + int(m * 1.5) + 6]
        sm = difflib.SequenceMatcher(None, pwords, win, autojunk=False)
        mapping = {}
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                for k in range(i2 - i1):
                    mapping[i1 + k] = s + j1 + k
            elif op == "replace" and (i2 - i1) == (j2 - j1):
                for k in range(i2 - i1):
                    if similar(pwords[i1 + k], win[j1 + k]):
                        mapping[i1 + k] = s + j1 + k
        if not mapping:
            continue
        score = len(mapping) / m
        first, last = min(mapping.values()), max(mapping.values())
        if score < TAKE_FLOOR or first > s + 2 or (first, last) in seen:
            continue
        seen.add((first, last))
        out.append((round(score, 3), first, last, mapping))
    return out


def choose_take(takes):
    """The best take; among takes within TAKE_TIE of the best, the last one (his retake wins)."""
    if not takes:
        return None
    best = max(t[0] for t in takes)
    return max((t for t in takes if t[0] >= best - TAKE_TIE), key=lambda t: t[1])


def line_spans(lines, mapping, heard):
    """[(start_s, end_s) or None] per line from the word mapping of one take."""
    spans, k = [], 0
    for line in lines:
        n = len(words(line))
        idx = [mapping[k + j] for j in range(n) if (k + j) in mapping]
        lead = next((j for j in range(n) if (k + j) in mapping), n)
        k += n
        if not idx:
            spans.append(None); continue
        a = min(idx)
        start = heard[a][1]
        if lead:
            # his first word(s) were heard but not recognized: start where they were heard, or back off by his pace
            b = a - lead
            if b >= 0 and heard[b][1] >= start - 0.6 * lead - 0.3:
                start = heard[b][1]
            else:
                start = max(0.0, start - 0.35 * lead)
        z = max(idx)
        end = heard[z][2]
        trail = next((j for j in range(n) if (k - 1 - j) in mapping), 0)
        if trail:
            c = z + trail
            end = heard[c][2] if c < len(heard) and heard[c][2] <= end + 0.6 * trail + 0.3 else end + 0.35 * trail
        spans.append((start, end))
    return spans


def cut_points(spans, db, sil, total_s):
    """Clip [start, end] per line, cut in the breath between lines (a silence when there is one, else the quietest
    10 ms), so no clip clips a word."""
    known = [s for s in spans if s]
    if not known:
        return [None] * len(spans)
    ends, starts = [], []   # per gap: where line i ends, where line i + 1 starts
    for i in range(len(spans) - 1):
        a, b = spans[i], spans[i + 1]
        if not a or not b:
            ends.append(None); starts.append(None); continue
        lo, hi = a[1] - 0.15, b[0] - 0.02
        inside = sorted(x for x in sil if x[1] > lo and x[0] < hi)
        if inside:
            # several pauses means something unscripted was said between the lines ("damn", a page turn):
            # line i ends in the first pause, line i + 1 starts in the last, and what sits between is dropped
            f, l = inside[0], inside[-1]
            ends.append((max(f[0], lo) + min(f[1], hi)) / 2)
            starts.append((max(l[0], lo) + min(l[1], hi)) / 2)
        else:
            q = quietest(db, lo, max(hi, lo + 0.02))
            ends.append(q); starts.append(q)
    first, last = spans[0], spans[-1]
    start = None
    if first:
        # only the breath right before his first word: reaching further back catches the tail of a false start
        before = [x for x in sil if first[0] - 0.45 <= x[1] <= first[0] + 0.25]
        start = (before[-1][1] - 0.10) if before else quietest(db, max(0.0, first[0] - 0.45), first[0] - 0.03)
        start = max(0.0, min(start, first[0] - 0.05))
    end = None
    if last:
        after = [x for x in sil if last[1] - 0.25 <= x[0] <= last[1] + 0.45]
        end = (after[0][0] + 0.30) if after else quietest(db, last[1] + 0.03, min(total_s, last[1] + 0.45))
        end = min(total_s, max(end, last[1] + 0.05))
    out = []
    for i, s in enumerate(spans):
        if not s:
            out.append(None); continue
        a = start if i == 0 else starts[i - 1]
        b = end if i == len(spans) - 1 else ends[i]
        a = a if a is not None else s[0] - 0.2
        b = b if b is not None else s[1] + 0.3
        out.append((round(max(0.0, a), 3), round(min(total_s, b), 3)))
    return out


def joined(spans, sil, breath=0.18):
    """Per gap between lines: True when he ran the two lines together with no breath. Those lines are also cut as one
    clip, so a post that shows both keeps his phrasing instead of a seam in the middle of a sentence."""
    out = []
    for a, b in zip(spans, spans[1:]):
        if not a or not b:
            out.append(False); continue
        lo, hi = a[1] - 0.1, b[0] + 0.1
        out.append(not any(min(x[1], hi) - max(x[0], lo) >= breath for x in sil))
    return out


MASTER_FILTERS = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-21dB:ratio=2.5:attack=15:release=200:makeup=2"


def cmd_cut(memos, plan=None, out=None):
    plan = plan or load_plan()
    out = out or work_dir()
    lines_dir = os.path.join(out, "lines")
    os.makedirs(lines_dir, exist_ok=True)
    heard, sources = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for n, memo in enumerate(memos):
            print(f"reading {os.path.basename(memo)} ...", flush=True)
            a16 = decode(memo, AN, os.path.join(tmp, f"a{n}.wav"), "highpass=f=80")
            m48 = decode(memo, SR, os.path.join(lines_dir, f"_master{n}.wav"), MASTER_FILTERS)
            sam, _ = read_pcm(a16)
            db = energy_db(sam, AN)
            total = len(sam) / AN
            got = TRANSCRIBE(a16, tmp)
            sources.append({"memo": memo, "master": m48, "db": db, "sil": silences(db), "total": total})
            heard += [(w, s, e, n) for (w, s, e) in got]
    flat = [(w, s, e) for (w, s, e, _) in heard]
    takes, missing = {}, []
    masters = {}
    for p in plan["passages"]:
        pw = [w for l in p["lines"] for w in words(l)]
        t = choose_take(takes_of(pw, flat))
        if not t:
            missing.append(p); continue
        score, first, last, mapping = t
        n = heard[first][3]
        if any(heard[i][3] != n for i in mapping.values()):
            mapping = {k: v for k, v in mapping.items() if heard[v][3] == n}
        src = sources[n]
        spans = line_spans(p["lines"], mapping, flat)
        cuts = cut_points(spans, src["db"], src["sil"], src["total"])
        if n not in masters:
            masters[n] = read_pcm(src["master"])[0]
        clips = []
        for i, (line, c) in enumerate(zip(p["lines"], cuts)):
            if not c:
                clips.append({"text": line, "clip": None}); continue
            seg = masters[n][int(c[0] * SR):int(c[1] * SR)]
            path = os.path.join(lines_dir, f"{p['id']}__L{i + 1:02d}.wav")
            write_pcm(path, fade(seg), SR)
            clips.append({"text": line, "clip": os.path.relpath(path, out), "from_s": c[0], "to_s": c[1],
                          "dur_s": round(len(seg) / SR, 3)})
        runs, j = [], 0
        tied = joined(spans, src["sil"])
        while j < len(clips):
            k = j
            while k < len(tied) and tied[k] and clips[k + 1]["clip"] and clips[j]["clip"]:
                k += 1
            if k > j:
                seg = masters[n][int(cuts[j][0] * SR):int(cuts[k][1] * SR)]
                path = os.path.join(lines_dir, f"{p['id']}__L{j + 1:02d}-L{k + 1:02d}.wav")
                write_pcm(path, fade(seg), SR)
                runs.append({"lines": list(range(j, k + 1)), "clip": os.path.relpath(path, out),
                             "dur_s": round(len(seg) / SR, 3)})
            j = k + 1
        takes[p["id"]] = {"memo": os.path.basename(src["memo"]), "score": score, "takes_heard": len(takes_of(pw, flat)),
                          "lines": clips, "runs": runs}
    rec = {"session": SESSION, "memos": [os.path.basename(m) for m in memos], "passages": takes,
           "missing": [p["id"] for p in missing]}
    json.dump(rec, open(os.path.join(out, "takes.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    found = len(takes)
    print(f"\nfound {found} of {len(plan['passages'])} passages")
    for pid, t in takes.items():
        holes = [c["text"] for c in t["lines"] if not c["clip"]]
        flag = f"  (line not heard: {holes[0]!r})" if holes else ""
        print(f"  ok  {pid}  {t['score']:.0%} of his words heard, {t['takes_heard']} take(s){flag}")
    for p in missing:
        print(f"  MISSING  {p['id']}  {p['title']}: \"{p['lines'][0]}\"")
    print(f"\nclips: {lines_dir}")
    return rec


def fade(seg, ms=8):
    n = min(len(seg) // 2, int(SR * ms / 1000))
    seg = array.array("h", seg)
    for i in range(n):
        g = i / n
        seg[i] = int(seg[i] * g)
        seg[-1 - i] = int(seg[-1 - i] * g)
    return seg


# ---------------------------------------------------------------- when each line appears on screen

def ocr_words(png):
    """Words visible on a frame. Apple Vision on his Mac (scripts/onscreen.py); tesseract anywhere else."""
    if sys.platform == "darwin" and os.environ.get("LABEAU_VOICE_OCR") != "tesseract":
        import onscreen
        items = onscreen.read_frame(png).get("items", [])
        return words(" ".join(it["text"] for it in items))
    try:   # one thread each (frames run in parallel); a frame of pure footage noise can stall it, so cap the read
        r = subprocess.run(["tesseract", png, "-", "--psm", "11"], capture_output=True, text=True, timeout=8,
                           env=dict(os.environ, OMP_THREAD_LIMIT="1"))
    except subprocess.TimeoutExpired:
        return []
    return words(r.stdout)


def file_key(path):
    st = os.stat(path)
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
    return f"{st.st_size}:{h.hexdigest()[:16]}"


def media_seconds(path):
    r = run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(r.stdout.strip() or 0)


def visible(lines, seen):
    """Per line: is it on this frame? All his lines are aligned against the frame's words in order (so a repeated line
    counts where it stands). A line is on when half its words are read, or its first word when that word is a real
    word (3+ letters) or is read with the word after it: his type fades in word by word, so the first word is the
    moment the line arrives."""
    a = [(i, w) for i, l in enumerate(lines) for w in words(l)]
    hit = [0] * len(lines)
    first = [False] * len(lines)
    starts, k = {}, 0
    for i, l in enumerate(lines):
        starts[i] = k; k += len(words(l))
    sm = difflib.SequenceMatcher(None, [w for _, w in a], seen, autojunk=False)
    for blk in sm.get_matching_blocks():
        for j in range(blk.size):
            li = a[blk.a + j][0]
            hit[li] += 1
            if blk.a + j == starts[li] and (len(a[blk.a + j][1]) >= 3 or j + 1 < blk.size):
                first[li] = True    # a real word, or a short one ("I'm", "My") read together with the next
    return [h >= 1 and (f or h >= math.ceil(len(words(lines[i])) / 2)) for i, (h, f) in enumerate(zip(hit, first))]


def settle(times_on):
    """First/last on-time per line from every frame time it was read, keeping onsets in reading order: a line can't
    arrive before the line above it, so a stray early read (one short word found in the footage) is skipped."""
    on, off, prev = [], [], 0.0
    for ts in times_on:
        later = [t for t in ts if t >= prev]
        on.append(later[0] if later else None)
        off.append(ts[-1] if ts else None)
        prev = later[0] if later else prev
    return on, off


def scan_onsets(video, lines, fps=FPS_SCAN, reader=None):
    """{"onsets": [s|None], "offsets": [s|None], "duration": s}: first and last moment each line is readable."""
    dur = media_seconds(video)
    seen_at = [[] for _ in lines]
    with tempfile.TemporaryDirectory() as tmp:
        frames = _frames(video, fps, tmp, prepared=reader is None and not _vision())
        for n, png in enumerate(frames):
            t = round(n / fps, 2)
            got = (reader or ocr_words)(png)
            for i, v in enumerate(visible(lines, got)):
                if v:
                    seen_at[i].append(t)
    on, off = settle(seen_at)
    return {"onsets": on, "offsets": off, "duration": round(dur, 3)}


def _vision():
    return sys.platform == "darwin" and os.environ.get("LABEAU_VOICE_OCR") != "tesseract"


def _frames(video, fps, tmp, prepared):
    """Frame files to read, in time order. Vision reads the frames as they are. For tesseract (black ink on white
    paper) each frame is thresholded in the same ffmpeg pass: his words are light on dark grounds, often over moving
    footage under a veil, so dark frames keep only the bright type and light frames only the dark type."""
    if not prepared:
        run([tool("ffmpeg"), "-nostdin", "-v", "error", "-i", video, "-vf", f"fps={fps},format=gray", os.path.join(tmp, "f%05d.png")])
        return [os.path.join(tmp, f) for f in sorted(os.listdir(tmp)) if f.endswith(".png")]
    graph = (f"[0:v]fps={fps},format=gray,split=3[a][b][c];[a]scale=16:28,format=gray[s];"
             "[b]lutyuv=y='if(gt(val,150),0,255)'[d];[c]lutyuv=y='if(lt(val,110),0,255)'[l]")
    run([tool("ffmpeg"), "-nostdin", "-v", "error", "-i", video, "-filter_complex", graph,
         "-map", "[s]", "-f", "rawvideo", os.path.join(tmp, "small.raw"),
         "-map", "[d]", os.path.join(tmp, "d%05d.png"), "-map", "[l]", os.path.join(tmp, "l%05d.png")])
    small = open(os.path.join(tmp, "small.raw"), "rb").read()
    px = 16 * 28
    out = []
    for n in range(len(small) // px):
        mean = sum(small[n * px:(n + 1) * px]) / px
        out.append(os.path.join(tmp, f"{'d' if mean < 128 else 'l'}{n + 1:05d}.png"))
    return [f for f in out if os.path.exists(f)]


def load_onsets():
    try:
        return json.load(open(ONSETS, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def onsets_for(video, lines, cache=None, save=True):
    cache = load_onsets() if cache is None else cache
    key = f"{file_key(video)}|{hashlib.sha1(' / '.join(lines).encode()).hexdigest()[:10]}"
    if key not in cache:
        cache[key] = dict(scan_onsets(video, lines), file=os.path.basename(video))
        if save:
            os.makedirs(os.path.dirname(ONSETS), exist_ok=True)
            json.dump(cache, open(ONSETS, "w", encoding="utf-8"), indent=1)
    return cache[key]


def slot_files(slot):
    return [os.path.join(ASSETS, f) for f in slot.get("files", []) if os.path.exists(os.path.join(ASSETS, f))]


def cmd_onsets(only=None, plan=None):
    plan = plan or load_plan()
    cache = load_onsets()
    for slot in plan["slots"]:
        if slot["voice"] not in ("new", "ab-test") or (only and slot["placement"] != only):
            continue
        texts = [t for _, _, t in slot_lines(plan, slot)]
        for f in slot_files(slot):
            o = onsets_for(f, texts, cache)
            print(f"{slot['placement']}  {os.path.basename(f)}  onsets {o['onsets']}", flush=True)


# ---------------------------------------------------------------- laying the voice onto a video

def place(onsets, offsets, durs, video_s):
    """Start time per line clip, and the seconds to hold the last frame. A line never starts before it is on screen,
    never overlaps the line before, and the first starts inside the first second when the screen allows it."""
    starts, t = [], 0.0
    for i, d in enumerate(durs):
        o = onsets[i] if i < len(onsets) and onsets[i] is not None else None
        if i == 0:
            s = max(0.10, o if o is not None else 0.25)
        else:
            s = max(t + GAP_S, (o + 0.05) if o is not None else t + 0.30)
        starts.append(round(s, 3))
        t = s + d
    hold = max(0.0, round(t + 0.8 - video_s, 3)) if t > video_s - 0.4 else 0.0
    late = [i for i, s in enumerate(starts) if i < len(offsets) and offsets[i] is not None and s > offsets[i] + 0.2]
    return starts, hold, late


def integrated(path):
    r = subprocess.run([tool("ffmpeg"), "-nostdin", "-hide_banner", "-i", path, "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    return float(m[-1]) if m else -70.0


def loudnorm(src, dst):
    """His voice to -14 LUFS integrated, peaks held under -1.5 dB (all his voice posts match; agreed with the DP-F8
    thread Oct 24): a clean gain into a peak limiter, measured again and nudged once when the limiter ate some of it.
    Speech keeps its own dynamics (no loudnorm pumping between lines)."""
    limit = 10 ** (TP / 20)
    gain = 0.0
    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(3):
            have = integrated(src) if gain == 0.0 else integrated(os.path.join(tmp, "v.wav"))
            if have <= -70:
                break
            if gain and abs(LUFS - have) < 0.5:
                break
            gain += LUFS - have
            run([tool("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", src, "-af",
                 f"volume={gain:.2f}dB,alimiter=limit={limit:.3f}:attack=2:release=60:level=false",
                 "-ar", str(SR), "-ac", "1", os.path.join(tmp, "v.wav")])
        final = os.path.join(tmp, "v.wav") if gain else src
        run([tool("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", final, "-ar", str(SR), "-ac", "2",
             "-c:a", "aac", "-b:a", "192k", dst])


def video_md5(path):
    r = run([tool("ffmpeg"), "-nostdin", "-v", "error", "-i", path, "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"])
    return r.stdout.strip()


def lay_one(video, line_clips, onsets, offsets, out_path, root):
    """Build one voiced copy. line_clips: [path]. Returns a report dict."""
    vs = media_seconds(video)
    clips = [read_pcm(os.path.join(root, c))[0] for c in line_clips]
    durs = [len(c) / SR for c in clips]
    starts, hold, late = place(onsets, offsets, durs, vs)
    total = vs + hold
    buf = array.array("h", bytes(2 * int(total * SR + 1)))
    for s, c in zip(starts, clips):
        i = int(s * SR)
        buf[i:i + len(c)] = c[:max(0, len(buf) - i)]
    with tempfile.TemporaryDirectory() as tmp:
        raw, aac = os.path.join(tmp, "voice.wav"), os.path.join(tmp, "voice.m4a")
        write_pcm(raw, buf, SR)
        loudnorm(raw, aac)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        part = out_path + ".part.mp4"
        if hold > 0:
            run([tool("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", video, "-i", aac, "-filter_complex",
                 f"[0:v]tpad=stop_mode=clone:stop_duration={hold:.3f}[v]", "-map", "[v]", "-map", "1:a",
                 "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30",
                 "-c:a", "copy", "-t", f"{total:.3f}", "-movflags", "+faststart", part])
        else:
            run([tool("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", video, "-i", aac, "-map", "0:v:0", "-map", "1:a:0",
                 "-c", "copy", "-t", f"{vs:.3f}", "-movflags", "+faststart", part])
        os.replace(part, out_path)
    rep = {"file": os.path.basename(out_path), "voice_starts": starts, "first_word_s": starts[0] if starts else None,
           "hold_s": hold, "late_lines": late, "seconds": round(total, 2)}
    rep["picture_identical"] = (video_md5(video) == video_md5(out_path)) if hold == 0 else "held last frame"
    return rep


def check_heard(path, lines):
    try:
        import audio_readback as AR
        return AR.check_audio(path, lines)
    except Exception as e:  # advisory, never blocks a build
        return {"status": "na", "why": f"audio check unavailable ({type(e).__name__})"}


def units(sl, takes):
    """What gets laid for a slot's lines: [clip], [[line index into sl]]. Lines he read in one breath go down as one
    clip at the first one's onset when the post shows them all; otherwise each line is its own clip."""
    clips, groups, j = [], [], 0
    while j < len(sl):
        pid, i, _ = sl[j]
        t = takes.get(pid)
        best = None
        for r in (t or {}).get("runs", []):
            if r["lines"][0] == i and all(j + m < len(sl) and sl[j + m][0] == pid and sl[j + m][1] == r["lines"][m]
                                          for m in range(len(r["lines"]))):
                if not best or len(r["lines"]) > len(best["lines"]):
                    best = r
        if best:
            clips.append(best["clip"]); groups.append(list(range(j, j + len(best["lines"])))); j += len(best["lines"])
            continue
        c = t["lines"][i].get("clip") if t and i < len(t["lines"]) else None
        clips.append(c); groups.append([j]); j += 1
    return clips, groups


def cmd_lay(only=None, plan=None, out=None, check=True):
    plan = plan or load_plan()
    out = out or work_dir()
    takes = json.load(open(os.path.join(out, "takes.json"), encoding="utf-8"))["passages"]
    stale = stale_fragments(plan)
    cache = load_onsets()
    rows = []
    for slot in plan["slots"]:
        if slot["voice"] not in ("new", "ab-test") or (only and slot["placement"] != only):
            continue
        sl = slot_lines(plan, slot)
        why = None
        if any(f in stale for f in slot["fragments"]):
            why = "words changed since he recorded: " + ", ".join(f for f in slot["fragments"] if f in stale)
        clips, groups = units(sl, takes)
        if None in clips:
            pid, i, _ = sl[groups[clips.index(None)][0]]
            why = why or f"not recorded yet: {pid} line {i + 1}"
        files = slot_files(slot)
        if not files:
            why = why or "video not built yet (run lay again after the batch is staged)"
        if why:
            rows.append({"placement": slot["placement"], "date": slot["date"], "file": "", "status": "skipped", "why": why})
            print(f"  skip  {slot['placement']} {slot['date']}: {why}")
            continue
        texts = [t for _, _, t in sl]
        for f in files:
            o = onsets_for(f, texts, cache)
            dst = os.path.join(out, "out", os.path.relpath(f, os.path.join(ASSETS, "04-posts")))
            rep = lay_one(f, clips, [o["onsets"][g[0]] for g in groups], [o["offsets"][g[-1]] for g in groups], dst, out)
            rep["late_lines"] = [groups[u][0] for u in rep["late_lines"]]
            heard = check_heard(dst, texts) if check else {"status": "na", "why": "not checked"}
            flags = []
            if rep["first_word_s"] is not None and rep["first_word_s"] > 1.0:
                flags.append(f"first word at {rep['first_word_s']} s")
            if rep["late_lines"]:
                flags.append(f"lines {', '.join(str(i + 1) for i in rep['late_lines'])} heard after they leave the screen")
            if rep["hold_s"] > MAX_HOLD_S:
                flags.append(f"read runs {rep['hold_s']} s past the video")
            if None in o["onsets"]:
                flags.append("some lines not read off the frames; timed by his pace")
            status = "review" if flags or heard["status"] == "fail" else "ok"
            rows.append({"placement": slot["placement"], "date": slot["date"], "file": os.path.relpath(dst, out),
                         "status": status, "why": "; ".join(flags), "first_word_s": rep["first_word_s"],
                         "hold_s": rep["hold_s"], "picture_identical": rep["picture_identical"],
                         "heard": heard["status"], "heard_why": heard.get("why", "")})
            print(f"  {status:6s} {slot['placement']} {slot['date']} {os.path.basename(f)}  voice from {rep['first_word_s']} s"
                  f"{', hold ' + str(rep['hold_s']) + ' s' if rep['hold_s'] else ''}  heard: {heard['status']}"
                  f"{'  ' + '; '.join(flags) if flags else ''}", flush=True)
    keys = ["placement", "date", "file", "status", "why", "first_word_s", "hold_s", "picture_identical", "heard", "heard_why"]
    with open(os.path.join(out, "lay-report.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    built = [r for r in rows if r["status"] in ("ok", "review")]
    print(f"\nbuilt {len(built)} voiced files ({sum(r['status'] == 'ok' for r in built)} ok, "
          f"{sum(r['status'] == 'review' for r in built)} to look at), skipped {sum(r['status'] == 'skipped' for r in rows)} slots")
    print(f"report: {os.path.join(out, 'lay-report.csv')}")
    return rows


# ---------------------------------------------------------------- staging (his hand)

def ledger_keys(path, keys):
    """The asset-ledger keys whose current version sits at path (else the key named after the file)."""
    same = lambda p: p and (p == os.path.abspath(path) or os.path.realpath(p) == os.path.realpath(path))
    hit = [key for key, k in keys.items() if k["current"] and same(k["versions"][k["current"]].get("path"))]
    stem = os.path.splitext(os.path.basename(path))[0]
    return hit or ([stem] if stem in keys else [])


def record(paths, ledger=None):
    """A voiced file is new bytes under the same ledger key; record it so validate doesn't flag "differs from file on
    disk" (Oct 24, 2026: same rule as rebuild_unsafe.record)."""
    try:
        import asset_ledger as AL
        L = AL.Ledger(ledger or AL.canonical_ledger())
        keys = L._replay()
    except Exception as e:
        print(f"ledger not updated: {e}", flush=True)
        return 0
    n = 0
    for path in paths:
        found = ledger_keys(path, keys)
        if not found:
            print(f"ledger: no key for {os.path.basename(path)}; add it with labeau asset add", flush=True)
        for key in found:
            try:
                if keys.get(key, {}).get("current") == AL.hash_file(path):
                    n += 1  # these exact bytes are already the current version: nothing to add
                    continue
                L.add(path, key, by="labeau voice-session", note=f"his voice read {SESSION}; old copy in _pre-voice-{SESSION}/")
                n += 1
            except Exception as e:
                print(f"ledger not updated for {os.path.basename(path)}: {e}", flush=True)
    return n


def cmd_stage(plan=None, out=None, ledger=None):
    plan = plan or load_plan()
    out = out or work_dir()
    staged = []
    rows = list(csv.DictReader(open(os.path.join(out, "lay-report.csv"), encoding="utf-8")))
    posts = os.path.join(ASSETS, "04-posts")
    done = 0
    for r in rows:
        if r["status"] not in ("ok", "review") or not r["file"]:
            continue
        slot = next(s for s in plan["slots"] if s["placement"] == r["placement"])
        if slot["voice"] != "new":
            continue          # the DP-F8 B copy stays in 03-review for the A/B
        src = os.path.join(out, r["file"])
        rel = os.path.relpath(src, os.path.join(out, "out"))
        dst = os.path.join(posts, rel)
        keep = os.path.join(os.path.dirname(dst), f"_pre-voice-{SESSION}", os.path.basename(dst))
        if not os.path.exists(src) or not os.path.exists(dst):
            continue
        if not os.path.exists(keep):
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            shutil.copy2(dst, keep)
        shutil.copy2(src, dst)
        staged.append(dst)
        done += 1
    n = record(staged, ledger) if staged else 0
    print(f"staged {done} voiced files into 04-posts; originals kept in each folder's _pre-voice-{SESSION}/; "
          f"{n} recorded in the asset ledger")


# ---------------------------------------------------------------- the plan

def cmd_check(plan=None):
    plan = plan or load_plan()
    slots = plan["slots"]
    ig = [s for s in slots if s["voice"] != "ab-test"]
    n_new = sum(s["voice"] == "new" for s in ig)
    n_old = sum(s["voice"] == "already" for s in ig)
    print(f"{len(ig)} Instagram/TikTok slots {plan['window'][0]} to {plan['window'][1]}: {n_new} get his new read, "
          f"{n_old} already carry his voice, {len(ig) - n_new - n_old} stay silent -> {(n_new + n_old) / len(ig):.0%} voiced")
    for s in ig:
        if s["voice"] == "silent":
            print(f"  silent  {s['placement']} {s['date']}: {s['why']}")
    stale = stale_fragments(plan)
    print(f"{len(plan['passages'])} passages to read; " + ("all words match fragments.csv" if not stale else f"CHANGED: {stale}"))
    built = sum(1 for s in slots if s["voice"] in ("new", "ab-test") and slot_files(s))
    print(f"{built} voiced slots have their video built today")
    return 0 if not stale else 1


# ---------------------------------------------------------------- selftest on his Mac

def cmd_selftest():
    """A synthetic read (macOS `say`) of two passages, with a stumble and a retake, through cut and lay on two real
    staged videos, into a temp folder. Proves whisper, Vision, ffmpeg and the timing on this Mac. Nothing is staged."""
    plan = load_plan()
    cands = [s for s in plan["slots"] if s["voice"] == "new" and slot_files(s) and len(s["fragments"]) == 1]
    cands.sort(key=lambda s: len(passage_of(plan, s["fragments"][0])["lines"]) * 10 - len(slot_lines(plan, s)))
    pick, pids = [], []
    for s in cands:
        p = passage_of(plan, s["fragments"][0])
        if p["id"] not in pids and len(pick) < 2:
            pick.append(s); pids.append(p["id"])
    if len(pick) < 2:
        print("FAIL: fewer than two built videos to test on"); return 1
    sub = {"passages": [p for p in plan["passages"] if p["id"] in pids],
           "slots": [dict(s, files=s["files"][:1]) for s in pick], "window": plan["window"]}
    tmp = tempfile.mkdtemp(prefix="voice-selftest-")
    parts = []
    for p in sub["passages"]:
        first = " ".join(p["lines"][0].split()[:3])
        parts.append(f"{first} [[slnc 900]] " + " [[slnc 700]] ".join(p["lines"]) + " [[slnc 1500]]")
    aiff = os.path.join(tmp, "read.aiff")
    run(["say", "-r", "150", "-o", aiff, " ".join(parts)])
    memo = os.path.join(tmp, "LaBeau Set test.m4a")
    run([tool("ffmpeg"), "-v", "error", "-y", "-i", aiff, "-c:a", "aac", memo])
    global ONSETS
    keep, ONSETS = ONSETS, os.path.join(tmp, "onsets.json")
    try:
        rec = cmd_cut([memo], sub, tmp)
        if rec["missing"]:
            print(f"FAIL: passages not found in the synthetic read: {rec['missing']}"); return 1
        rows = cmd_lay(None, sub, tmp)
    finally:
        ONSETS = keep
    built = [r for r in rows if r["status"] in ("ok", "review")]
    good = [r for r in built if r["heard"] == "pass" and r["picture_identical"] in (True, "True", "held last frame")
            and r["first_word_s"] is not None and float(r["first_word_s"]) <= 1.0]
    print(f"\n{'PASS' if len(good) == len(built) == len(pick) else 'FAIL'}: {len(good)} of {len(pick)} test videos voiced, "
          f"heard back in order, picture unchanged, voice inside the first second.  files: {tmp}/out")
    return 0 if len(good) == len(built) == len(pick) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="voice_session.py", description=__doc__.split("\n\n")[0])
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check")
    o = sp.add_parser("onsets"); o.add_argument("--only")
    c = sp.add_parser("cut"); c.add_argument("memos", nargs="+")
    l = sp.add_parser("lay"); l.add_argument("--only"); l.add_argument("--no-check", action="store_true")
    sp.add_parser("stage")
    sp.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return cmd_check()
    if a.cmd == "onsets":
        return cmd_onsets(a.only)
    if a.cmd == "cut":
        rec = cmd_cut(a.memos)
        return 0 if not rec["missing"] else 2
    if a.cmd == "lay":
        cmd_lay(a.only, check=not a.no_check); return 0
    if a.cmd == "stage":
        cmd_stage(); return 0
    if a.cmd == "selftest":
        return cmd_selftest()


if __name__ == "__main__":
    sys.exit(main())
