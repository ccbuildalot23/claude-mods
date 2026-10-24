"""Logic tests with stand-in models (no downloads). The real models run only on the Mac.

Run: HS_BRIDGE=<copy of grok-bridge> HS_CATALOG=<harness_map.csv> python -m unittest tests/test_hs.py
"""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
TMP = tempfile.mkdtemp()
os.environ["HS_INDEX"] = TMP
import hs  # noqa: E402


class FakeEmbedder:
    """Bag-of-words hashing into 256 dims: enough to exercise the vector path."""
    def encode(self, texts, normalize_embeddings=True, **_):
        out = np.zeros((len(texts), 256), dtype="float32")
        for r, t in enumerate(texts):
            for tok in hs.tokenize(t):
                out[r, int(hashlib.md5(tok.encode()).hexdigest(), 16) % 256] += 1
        n = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(n == 0, 1, n)


class FakeReranker:
    def predict(self, pairs):
        return [len(set(hs.tokenize(q)) & set(hs.tokenize(d))) for q, d in pairs]


hs.load_embedder = lambda: FakeEmbedder()
hs.load_reranker = lambda: FakeReranker()


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with redirect_stdout(io.StringIO()):
            hs.cmd_index(None)

    def test_private_and_creative_files_skipped(self):
        files = [hs.label(f) for f in hs.source_files()]
        self.assertTrue(files)
        for bad in ("chelsea", "freestyle", "/journal/", "/archive/", "/tools/"):
            self.assertFalse([f for f in files if bad in f.lower()], bad)

    def test_private_marker_skips(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.md").write_text("> PRIVATE, approved for Hermes only\nsecret")
        (d / "b.md").write_text("move private files later")
        old = hs.BRIDGE
        hs.BRIDGE = d
        try:
            self.assertFalse(hs.eligible(d / "a.md"))
            self.assertTrue(hs.eligible(d / "b.md"))
        finally:
            hs.BRIDGE = old

    def test_tokenizer_keeps_codes(self):
        t = hs.tokenize("See G2C-2026-10-19-002 and chromadb 1.5.9")
        self.assertIn("g2c-2026-10-19-002", t)
        self.assertIn("1.5.9", t)
        self.assertIn("g2c", t)

    def test_all_modes_return_files(self):
        s = hs.Searcher()
        for m in hs.MODES:
            top = s.files(s.search("G2C-2026-10-19-002", m), 5)
            self.assertEqual(len(top), len(set(top)))
        for m in ("bm25", "hybrid+rerank"):  # stand-in vectors are noise here
            top = s.files(s.search("G2C-2026-10-19-002", m), 5)
            self.assertEqual(len(top), len(set(top)))
            self.assertIn("grok-bridge/to-claude/G2C-2026-10-19-002-hermes-librarian.md", top, m)

    def test_gold_files_exist_in_index(self):
        s = hs.Searcher()
        indexed = {c[0] for c in s.chunks}
        for q in json.loads(hs.QUESTIONS.read_text()):
            self.assertTrue(set(q["gold"]) & indexed, q["id"])
            self.assertEqual(len(set(q["gold"]) - indexed), 0, (q["id"], set(q["gold"]) - indexed))

    def test_scoreboard_runs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                hs.cmd_scoreboard(type("A", (), {"publish": False})())
            except SystemExit:
                pass
        self.assertIn("| hybrid+rerank |", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
