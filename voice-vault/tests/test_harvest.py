import csv
import datetime as dt
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import diary_harvest as dh  # noqa: E402
import share_library as sl  # noqa: E402
import voice_vault as vv  # noqa: E402

WORDS = vv.DEFAULTS["private_words"]


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


class ShareTriggerTests(unittest.TestCase):
    def test_share_defaults_to_both(self):
        self.assertEqual(vv.route("Share. we were never lost, only early", WORDS)[:2],
                         ("share-both", "we were never lost, only early"))

    def test_share_brand_word(self):
        self.assertEqual(vv.route("Share LaBeau: red stems", WORDS)[:2], ("share-labeau", "red stems"))
        self.assertEqual(vv.route("share line, Chris - red stems", WORDS)[:2], ("share-chris", "red stems"))
        self.assertEqual(vv.route("Share both red stems", WORDS)[:2], ("share-both", "red stems"))

    def test_share_with_private_detail_is_held(self):
        dest, _, held = vv.route("Share my therapist said the door was open", WORDS)
        self.assertEqual(dest, "vault")
        self.assertTrue(held)

    def test_line_trigger_unchanged(self):
        self.assertEqual(vv.route("Line red stems", WORDS)[0], "line_bank")
        self.assertEqual(vv.route("Shared a meal today", WORDS)[0], "vault")


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lens = self.tmp / "lens.md"
        shutil.copy(HERE / "templates/hierophant-lens.md", self.lens)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_ei_weeks(self):
        self.assertEqual(sl.ei_week(dt.date(2026, 10, 24)), "setup")
        self.assertEqual(sl.ei_week(dt.date(2026, 10, 26)), "week 1")
        self.assertEqual(sl.ei_week(dt.date(2026, 11, 1)), "week 1")
        self.assertEqual(sl.ei_week(dt.date(2026, 11, 2)), "week 2")
        self.assertEqual(sl.ei_week(dt.date(2026, 12, 20)), "week 8")
        self.assertEqual(sl.ei_week(dt.date(2026, 12, 21)), "after")

    def test_candidates_verbatim_and_ids(self):
        lib = self.tmp / "sc/share-candidates.csv"
        line = '  the moon kept its receipts, "and" I kept mine '
        sl.append_candidates(lib, [{"line": line, "brand": "both", "source": "t", "written_on": dt.date(2026, 10, 27)}])
        sl.append_candidates(lib, [{"line": "two", "brand": "chris", "source": "t", "written_on": dt.date(2026, 10, 28)}])
        r = rows(lib)
        self.assertEqual(r[0]["line"], line)
        self.assertEqual(r[0]["ei_week"], "week 1")
        self.assertTrue(r[1]["id"].endswith("-002"))
        self.assertEqual({x["status"] for x in r}, {"share-candidate"})

    def test_lens_append_keeps_rest(self):
        before = self.lens.read_text()
        sl.append_lens(self.lens, "lens", ["warm, unhurried, home"], dt.date(2026, 10, 24))
        sl.append_lens(self.lens, "lens", ["second line"], dt.date(2026, 11, 28))
        sl.append_lens(self.lens, "echo", ["it feels like a letter"], dt.date(2026, 12, 11))
        after = self.lens.read_text()
        self.assertIn("- 2026-10-24 (setup): warm, unhurried, home\n- 2026-11-28 (week 5): second line\n<!-- harvest adds Chris's lines", after)
        self.assertIn("- 2026-12-11 (week 7): it feels like a letter\n<!-- harvest adds reader echoes", after)
        self.assertNotIn("(empty until Chris harvests his first Lens line)", after)
        self.assertNotIn("(empty until Chris harvests his first echo)", after)
        # Everything above the first section is untouched.
        head = before.split("## From Chris's pages")[0]
        self.assertTrue(after.startswith(head))


class IntakeAndHarvestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = vv.load_config(self.tmp / "none.json")
        self.cfg.update({
            "inbox": [str(self.tmp / "Voice Inbox")], "watch_readonly": [],
            "vault_inbox": str(self.tmp / "vault/Voice Inbox"),
            "diary_pages_dir": str(self.tmp / "vault/Diary Pages"),
            "line_bank_dir": str(self.tmp / "lb"), "line_audio_dir": str(self.tmp / "audio"),
            "share_library": str(self.tmp / "sc/share-candidates.csv"),
            "lens_file": str(self.tmp / "lens/hierophant-lens.md"),
            "state_file": str(self.tmp / "state/p.json"), "log_file": str(self.tmp / "state/log"),
        })
        Path(self.cfg["lens_file"]).parent.mkdir(parents=True)
        shutil.copy(HERE / "templates/hierophant-lens.md", self.cfg["lens_file"])
        inbox = self.tmp / "Voice Inbox"
        inbox.mkdir()
        shutil.copy(HERE / "templates/demo-page.png", inbox / "IMG_0001.png")
        (inbox / "share.txt").write_text("Share LaBeau: we were never lost, only early")
        old = time.time() - 60
        for p in inbox.iterdir():
            import os
            os.utime(p, (old, old))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def intake(self):
        reader = lambda p: ["the river does not apologize for the stone", "Call the trustee Monday", "unmarked private line"]
        return vv.run(self.cfg, reader=reader)

    def test_photo_goes_to_vault_only(self):
        self.assertEqual(self.intake(), 2)
        pages = list(Path(self.cfg["diary_pages_dir"]).iterdir())
        self.assertEqual(sorted(p.suffix for p in pages), [".md", ".png"])
        self.assertEqual(list((self.tmp / "Voice Inbox").iterdir()), [])
        # The photo's text did not reach the library; only the Share text drop did.
        r = rows(self.cfg["share_library"])
        self.assertEqual([(x["brand"], x["line"]) for x in r], [("labeau", "we were never lost, only early")])
        log = Path(self.cfg["log_file"]).read_text()
        self.assertNotIn("river", log)
        self.assertNotIn("never lost", log)

    def test_photo_without_reader_still_filed(self):
        def broken(p):
            raise RuntimeError("Apple Vision reader not installed")
        vv.run(self.cfg, reader=broken)
        note = next(Path(self.cfg["diary_pages_dir"]).glob("*.md"))
        self.assertIn("status: needs-harvest", note.read_text())
        self.assertIn("reading: none", note.read_text())

    def test_harvest_holds_then_saves(self):
        self.intake()
        page = dh.pending_pages(self.cfg)[0]
        payload = {"pages": [{"note": page["note"], "written_on": "2026-10-25", "lines": [
            {"text": "the river does not apologize for the stone", "tag": "both"},
            {"text": "Call the trustee Monday", "tag": "chris"},
            {"text": "warm, unhurried, home", "tag": "lens"},
        ]}]}
        first = dh.save(self.cfg, payload)
        self.assertFalse(first["written"])
        self.assertEqual(len(first["held"]), 1)
        self.assertEqual(len(rows(self.cfg["share_library"])), 1)  # only the earlier Share drop
        payload["skip_held"] = True
        second = dh.save(self.cfg, payload)
        self.assertTrue(second["written"])
        self.assertEqual(second["saved"], 2)
        r = rows(self.cfg["share_library"])
        self.assertEqual(r[-1]["line"], "the river does not apologize for the stone")
        self.assertEqual(r[-1]["ei_week"], "setup")
        self.assertNotIn("unmarked private line", Path(self.cfg["share_library"]).read_text())
        self.assertNotIn("trustee", Path(self.cfg["share_library"]).read_text())
        self.assertIn("2026-10-25 (setup): warm, unhurried, home", Path(self.cfg["lens_file"]).read_text())
        self.assertEqual(dh.pending_pages(self.cfg), [])
        note = Path(self.cfg["diary_pages_dir"]) / page["note"]
        self.assertIn("status: harvested", note.read_text())
        self.assertIn("held_at_harvest: names 'trustee'", note.read_text())

    def test_server_needs_key_and_binds_local(self):
        self.intake()
        server, url = dh.serve(self.cfg, open_browser=False)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            bad = url.split("?")[0] + "?k=wrong"
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(bad)
            self.assertEqual(e.exception.code, 403)
            html = urllib.request.urlopen(url).read().decode()
            self.assertIn("the river does not apologize", html)
            self.assertNotIn("/*DATA*/null", html)
            page = dh.pending_pages(self.cfg)[0]
            base = url.split("?")[0].rstrip("/")
            key = url.split("?k=")[1]
            photo = urllib.request.urlopen(f"{base}/photo/{urllib.parse.quote(page['photo'])}?k={key}")
            self.assertEqual(photo.headers["Content-Type"], "image/png")
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(f"{base}/photo/..%2F..%2Fsecret.png?k={key}")
        finally:
            server.shutdown()
            shutil.rmtree(server.cache_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
