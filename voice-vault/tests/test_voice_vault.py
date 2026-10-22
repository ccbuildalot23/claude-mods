import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import voice_vault as vv  # noqa: E402

WORDS = vv.DEFAULTS["private_words"]


class RouteTests(unittest.TestCase):
    def test_line_keeps_words_exactly(self):
        dest, body, held = vv.route("Line. the moon kept its receipts,  and I kept mine", WORDS)
        self.assertEqual(dest, "line_bank")
        self.assertEqual(body, "the moon kept its receipts,  and I kept mine")
        self.assertEqual(held, [])

    def test_labeau_spellings(self):
        for t in ("LaBeau: red stems", "Lebo, red stems", "La Beau line red stems", "line bank - red stems", "Poem line red stems"):
            self.assertEqual(vv.route(t, WORDS)[:2], ("line_bank", "red stems"), t)

    def test_default_is_private(self):
        self.assertEqual(vv.route("Remind me to call the bank", WORDS)[0], "vault")
        self.assertEqual(vv.route("Lines I keep thinking about", WORDS)[0], "vault")

    def test_private_trigger_stripped(self):
        self.assertEqual(vv.route("Private. today was hard", WORDS)[:2], ("vault", "today was hard"))

    def test_line_with_private_detail_is_held(self):
        for t in ("Line, my therapist said the door was open", "Line the trustee wants $400", "line call me 555-123-4567"):
            dest, _, held = vv.route(t, WORDS)
            self.assertEqual(dest, "vault", t)
            self.assertTrue(held, t)

    def test_empty_line_goes_to_vault(self):
        self.assertEqual(vv.route("Line.", WORDS)[0], "vault")


class SharedListTests(unittest.TestCase):
    def test_reads_privacy_preflight_lists(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "config").mkdir()
        (tmp / "config/private-names.txt").write_text("# names\nDana\n")
        (tmp / "voice-vault").mkdir()
        old = vv.HERE
        vv.HERE = tmp / "voice-vault"
        try:
            cfg = vv.load_config(tmp / "none.json")
        finally:
            vv.HERE = old
        self.assertIn("Dana", cfg["private_words"])
        self.assertEqual(vv.route("Line. Dana smiled", cfg["private_words"])[0], "vault")


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = dict(vv.DEFAULTS)
        self.cfg.update(
            inbox=[str(self.tmp / "inbox")],
            watch_readonly=[str(self.tmp / "memos")],
            vault_inbox=str(self.tmp / "vault"),
            line_bank_dir=str(self.tmp / "line-bank"),
            line_audio_dir=str(self.tmp / "voice-lines"),
            state_file=str(self.tmp / "state/processed.json"),
            log_file=str(self.tmp / "state/log"),
        )
        for d in ("inbox", "memos"):
            (self.tmp / d).mkdir()

    def audio(self, folder, name, data):
        p = self.tmp / folder / name
        p.write_bytes(data)
        old = time.time() - 60
        os.utime(p, (old, old))
        return p

    def test_files_both_routes_and_never_logs_words(self):
        texts = {b"a": "Line. salt on the window", b"b": "Private. the session with my therapist"}
        self.audio("inbox", "one.m4a", b"a")
        ro = self.audio("memos", "two.m4a", b"b")
        n = vv.run(self.cfg, transcriber=lambda p, c: texts[p.read_bytes()])
        self.assertEqual(n, 2)
        lines = list((self.tmp / "line-bank").glob("*.md"))
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].read_text().endswith("---\nsalt on the window\n"))
        self.assertEqual(len(list((self.tmp / "voice-lines").glob("*.m4a"))), 1)
        vault = list((self.tmp / "vault").glob("*.md"))
        self.assertEqual(len(vault), 1)
        self.assertIn("status: needs-intake", vault[0].read_text())
        self.assertFalse((self.tmp / "inbox/one.m4a").exists())  # inbox audio moved
        self.assertTrue(ro.exists())  # Voice Memos originals untouched
        log = (self.tmp / "state/log").read_text()
        self.assertNotIn("salt", log)
        self.assertNotIn("therapist", log)
        # second run files nothing new
        self.assertEqual(vv.run(self.cfg, transcriber=lambda p, c: texts[p.read_bytes()]), 0)

    def test_held_line_lands_in_vault_with_reason(self):
        self.audio("inbox", "x.m4a", b"x")
        vv.run(self.cfg, transcriber=lambda p, c: "LaBeau line the lawyer at dinner")
        self.assertFalse((self.tmp / "line-bank").exists())
        note = next((self.tmp / "vault").glob("*.md")).read_text()
        self.assertIn("held_from_line_bank: names 'lawyer'", note)

    def test_no_transcriber_leaves_audio(self):
        p = self.audio("inbox", "y.m4a", b"y")

        def boom(a, c):
            raise RuntimeError("no local transcriber installed")

        self.assertEqual(vv.run(self.cfg, transcriber=boom), 0)
        self.assertTrue(p.exists())
        self.assertEqual(json.loads((self.tmp / "state/processed.json").read_text()), {})

    def test_text_drop_skips_transcriber(self):
        self.audio("inbox", "dump.txt", "Line. porch light, no one home".encode())

        def boom(a, c):
            raise AssertionError("text should not be transcribed")

        self.assertEqual(vv.run(self.cfg, transcriber=boom), 1)
        note = next((self.tmp / "line-bank").glob("*Text Line.md")).read_text()
        self.assertIn("source: text-drop", note)
        self.assertTrue(note.endswith("---\nporch light, no one home\n"))

    def test_watch_since_skips_old_voice_memos(self):
        old = self.audio("memos", "old.m4a", b"old")
        os.utime(old, (time.time() - 86400 * 30,) * 2)
        self.audio("memos", "new.m4a", b"new")
        self.cfg["watch_since"] = vv.dt.datetime.fromtimestamp(time.time() - 86400).isoformat()
        self.assertEqual(vv.run(self.cfg, transcriber=lambda p, c: "Private. hi"), 1)
        self.assertTrue(old.exists())

    def test_fresh_file_waits_to_settle(self):
        (self.tmp / "inbox/z.m4a").write_bytes(b"z")
        self.assertEqual(vv.run(self.cfg, transcriber=lambda p, c: "Line hi"), 0)


if __name__ == "__main__":
    unittest.main()
