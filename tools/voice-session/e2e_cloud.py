"""Cloud end-to-end: synthetic memo (espeak-ng, word by word so we know every word's time) -> cut -> lay on real
staged videos -> verify timing, picture, loudness. whisper-cli is replaced by the known word times (with injected
recognizer errors); everything else is the real code path."""
import array, json, os, random, subprocess, sys, tempfile, wave
OPS = "/tmp/claude-0/ops"
os.environ["LABEAU_ASSETS"] = "/tmp/claude-0/assets"
os.environ["LABEAU_VOICE_WORK"] = "/tmp/claude-0/work"
os.environ["LABEAU_VOICE_OCR"] = "tesseract"
sys.path.insert(0, OPS + "/scripts")
import voice_session as V
random.seed(7)
plan = V.load_plan(OPS + "/data/voice/session-2026-10-25.json")
PICK = ["P4416", "P4476", "P4355", "P4462", "P4422"]
FULL = os.environ.get("FULL") == "1"
slots = [s for s in plan["slots"] if (s["voice"] in ("new", "ab-test") if FULL else s["placement"] in PICK)]
pids = []
for s in slots:
    for f in s["fragments"]:
        p = V.passage_of(plan, f)
        if p["id"] not in pids: pids.append(p["id"])
sub = {"passages": [p for p in plan["passages"] if p["id"] in pids], "slots": slots, "window": plan["window"]}
print("passages", pids)

SR = 22050
def say(word, speed):
    with tempfile.NamedTemporaryFile(suffix=".wav") as t:
        subprocess.run(["espeak-ng", "-s", str(speed), "-w", t.name, word], check=True)
        with wave.open(t.name) as w:
            a = array.array("h"); a.frombytes(w.readframes(w.getnframes())); r = w.getframerate()
    # trim espeak's own leading/trailing silence
    thr = 300
    i = next((k for k, x in enumerate(a) if abs(x) > thr), 0); j = len(a) - next((k for k, x in enumerate(reversed(a)) if abs(x) > thr), 0)
    return a[i:j], r

audio = array.array("h"); truth = []
noise = lambda n: array.array("h", (random.randint(-40, 40) for _ in range(n)))
def pause(s): audio.extend(noise(int(SR * s)))
def speak(text, speed=150, record=True):
    for w in text.split():
        seg, r = say(w, speed); assert r == SR
        t0 = len(audio) / SR; audio.extend(seg); t1 = len(audio) / SR
        if record: truth.append((w, t0, t1))
        pause(0.06)

pause(1.0)
speak("okay this is set one")           # chatter that is not his poem
pause(1.2)
skip = "S3-01"                          # he forgets one passage: cut must say MISSING
for p in sub["passages"]:
    if p["id"] == skip: continue
    if p["id"] == "S2-01":              # a stumble, then the retake
        speak(" ".join(p["lines"][0].split()[:3]) + " and Im stuck uh"); pause(0.9); speak("sorry again"); pause(0.8)
    for l in p["lines"]:
        speak(l, speed=random.choice([140, 150, 160])); pause(random.choice([0.5, 0.7, 0.9]))
    pause(2.0)
memo = "/tmp/claude-0/work_memo.wav"
with wave.open(memo, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(audio.tobytes())
m4a = "/tmp/claude-0/LaBeau Set 1.m4a"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", memo, "-c:a", "aac", "-b:a", "128k", m4a], check=True)

ERRS = {"rut": "rot", "victim": "victims", "Rest": "rest", "mirror": "mere"}
def fake_whisper(wav16, tmp):
    out = []
    for w, a, b in truth:
        for n in V.words(ERRS.get(w.strip(",.?!"), w)):
            out.append((n, a + 0.03, b + 0.05))   # whisper times are a little late; the cutter must not care
    return out
V.TRANSCRIBE = fake_whisper
os.makedirs("/tmp/claude-0/work", exist_ok=True)
V.ONSETS = OPS + "/data/voice/onsets.json" if FULL else "/tmp/claude-0/work/onsets.json"
rec = V.cmd_cut([m4a], sub)
assert rec["missing"] == [skip], rec["missing"]
# the retake, not the stumble, must be the take used
t = rec["passages"]["S2-01"]
first_clip_from = t["lines"][0]["from_s"]
retake_start = [truth[i][1] for i in range(len(truth) - 3) if [w for w, _, _ in truth[i:i + 4]] == ["My", "health", "is", "leaving"]][-1]
assert abs(first_clip_from - retake_start) < 0.6, (first_clip_from, retake_start)
# every clip must contain its whole line: start before the first word, end after the last word
for pid, t in rec["passages"].items():
    p = next(p for p in sub["passages"] if p["id"] == pid)
    for line, c in zip(p["lines"], t["lines"]):
        assert c["clip"], (pid, line)
# clip bounds hold the whole line (last spoken occurrence of that line in the memo)
tw = [(n, a, b) for w, a, b in truth for n in V.words(w)]
bad = 0
for pid, t in rec["passages"].items():
    p = next(p for p in sub["passages"] if p["id"] == pid)
    allw = [w for l in p["lines"] for w in V.words(l)]
    occ = [i for i in range(len(tw) - len(allw) + 1) if [x[0] for x in tw[i:i + len(allw)]] == allw]
    pos = occ[-1]
    for line, c in zip(p["lines"], t["lines"]):
        lw = V.words(line)
        i = pos; pos += len(lw); a, b = tw[i][1], tw[i + len(lw) - 1][2]
        if not (c["from_s"] <= a + 0.02 and c["to_s"] >= b - 0.02):
            bad += 1; print("CLIPPED", pid, line, c["from_s"], c["to_s"], a, b)
assert bad == 0
print("cut OK: every clip holds its whole line")

rows = V.cmd_lay(None, sub, check=False)
built = [r for r in rows if r["status"] in ("ok", "review")]
print(json.dumps(rows, indent=1)[:3000])
for r in built:
    out = os.path.join("/tmp/claude-0/work", r["file"])
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.split()
    assert "audio" in pr and "video" in pr, pr
    assert float(r["first_word_s"]) <= 1.0, r
    if r["hold_s"] in (0, 0.0, "0", "0.0"):
        assert r["picture_identical"] is True, r
lufs = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", os.path.join("/tmp/claude-0/work", built[0]["file"]), "-af", "ebur128", "-f", "null", "-"],
                      capture_output=True, text=True).stderr.split("Integrated loudness:")[1].split("LUFS")[0]
print("integrated loudness of first output:", lufs.strip())
skipped = [r for r in rows if r["status"] == "skipped"]
assert any("S3-01" in r["why"] for r in skipped), skipped
if FULL:
    import collections
    print(collections.Counter(r["status"] for r in rows))
    for r in rows:
        if r["status"] != "ok": print(r["placement"], r["date"], r["status"], r["why"])
print(f"E2E OK: {len(built)} files built, {len(skipped)} skipped as expected")
