"""Word-timed transcription with sherpa-onnx parakeet (cloud stand-in for whisper-cli)."""
import subprocess, sys, json, numpy as np, sherpa_onnx
M = "/tmp/claude-0/asr/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
SR = 16000

def load(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)

def chunks(x, target=22.0, slack=6.0):
    """Split at the quietest 50 ms near every `target` seconds."""
    out, a, n = [], 0, len(x)
    win = int(0.05 * SR)
    while a < n:
        if n - a <= int((target + slack) * SR):
            out.append((a, n)); break
        lo, hi = a + int((target - slack) * SR), a + int((target + slack) * SR)
        seg = x[lo:hi]
        e = np.convolve(seg ** 2, np.ones(win), "valid")
        b = lo + int(np.argmin(e)) + win // 2
        out.append((a, b)); a = b
    return out

def transcribe(path):
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f"{M}/encoder.int8.onnx", decoder=f"{M}/decoder.int8.onnx", joiner=f"{M}/joiner.int8.onnx",
        tokens=f"{M}/tokens.txt", model_type="nemo_transducer", num_threads=4)
    x = load(path)
    words = []
    for a, b in chunks(x):
        s = rec.create_stream(); s.accept_waveform(SR, x[a:b]); rec.decode_stream(s)
        r = s.result
        t0 = a / SR
        toks, ts = list(r.tokens), list(r.timestamps)
        cur = None
        for i, (tok, t) in enumerate(zip(toks, ts)):
            start = t0 + t
            if tok.startswith("▁") or tok.startswith(" ") or cur is None:
                if cur: words.append(cur)
                cur = [tok.lstrip("▁ "), start, start + 0.08]
            else:
                cur[0] += tok
            cur[2] = start + 0.08
        if cur: words.append(cur)
    # a word ends shortly before the next begins (cap 0.6 s past its last token)
    for i, w in enumerate(words):
        nxt = words[i + 1][1] if i + 1 < len(words) else w[2] + 0.4
        w[2] = round(min(max(w[2] + 0.12, w[2]), nxt - 0.02, w[2] + 0.6), 3)
        w[1] = round(w[1], 3)
    return [tuple(w) for w in words if w[0]]

if __name__ == "__main__":
    w = transcribe(sys.argv[1])
    json.dump(w, open(sys.argv[2], "w"))
    print(len(w), "words;", " ".join(x[0] for x in w[:60]))
