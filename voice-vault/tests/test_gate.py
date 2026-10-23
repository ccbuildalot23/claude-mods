import datetime as dt
import email.message
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import journal_gate as g  # noqa: E402
import share_library as sl  # noqa: E402
import voice_vault as vv  # noqa: E402

WORDS = vv.DEFAULTS["private_words"]
MONDAY = dt.datetime(2026, 10, 26, 7, 5)
PAGE = [("the river does not apologize for the stone", 0.92),
        ("I called Marcus after the meeting", 0.88),
        ("we were nevr lost, only early", 0.31),
        ("tasha said the porch light stays on", 0.9)]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        g.STATE = self.tmp / "state"
        self.cfg = vv.load_config(self.tmp / "none.json")
        self.cfg.update({
            "inbox": [str(self.tmp / "Voice Inbox")], "watch_readonly": [],
            "vault_inbox": str(self.tmp / "vault"), "line_bank_dir": str(self.tmp / "lb"),
            "line_audio_dir": str(self.tmp / "audio"), "diary_pages_dir": str(self.tmp / "Journal Pages"),
            "share_library": str(self.tmp / "sc/share-candidates.csv"),
            "lens_file": str(self.tmp / "lens/hierophant-lens.md"),
            "state_file": str(self.tmp / "vvstate/p.json"), "log_file": str(self.tmp / "vvstate/log"),
            "known_names": ["Marcus"], "roles": {"tasha": ["my sister", "my big sister"]}, "not_names": set(),
        })
        Path(self.cfg["lens_file"]).parent.mkdir(parents=True)
        shutil.copy(HERE / "templates/hierophant-lens.md", self.cfg["lens_file"])
        inbox = self.tmp / "Voice Inbox"
        inbox.mkdir()
        shutil.copy(HERE / "templates/demo-page.png", inbox / "IMG_0001.png")
        old = time.time() - 60
        os.utime(inbox / "IMG_0001.png", (old, old))
        self.sent = []

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def mailer(self, subject, body):
        self.sent.append((subject, body))

    def rows(self):
        return sl.load(Path(self.cfg["share_library"]))

    def monday(self, replies=()):
        return g.run(self.cfg, now=MONDAY, reader=lambda p: PAGE, replies=list(replies), mailer=self.mailer)


class NameTests(unittest.TestCase):
    cfg = {"known_names": ["marcus"], "roles": {"tasha": ["my sister"]}, "not_names": {"atlanta"}}

    def test_finds_listed_and_capitalised_names(self):
        self.assertEqual(g.find_names("I called Marcus after", self.cfg), ["Marcus"])
        self.assertEqual(g.find_names("tasha said so", self.cfg), ["tasha"])
        self.assertEqual(g.find_names("When I was out with Dre", self.cfg), ["Dre"])
        self.assertEqual(g.find_names("I told James's mother", self.cfg), ["James"])

    def test_leaves_ordinary_capitals_alone(self):
        for t in ("The river does not apologize", "Mom kept the receipts. Grace is a verb",
                  "On Sunday I prayed to God", "I drove through Atlanta"):
            self.assertEqual(g.find_names(t, self.cfg), [], t)

    def test_roles_from_his_list_come_first(self):
        self.assertEqual(g.role_options(["tasha"], self.cfg)[:2], ["my sister", "a friend"])

    def test_swap_keeps_everything_else(self):
        self.assertEqual(g.swap_names("I told James's mother, James", ["James"], "my brother"),
                         "I told my brother's mother, my brother")


class ParseTests(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(g.parse("strike 3, 5 and 7"), [("strike", n, "") for n in "357"])
        self.assertEqual(g.parse("3 b, 5 a"), [("pick", "3", "b"), ("pick", "5", "a")])
        self.assertEqual(g.parse("3: my coach, always"), [("role", "3", "my coach, always")])
        self.assertEqual(g.parse("4 fix: the river, unbothered"), [("fix", "4", "the river, unbothered")])
        self.assertEqual(g.parse("ok 4; lens 2"), [("ok", "4", ""), ("lens", "2", "")])

    def test_ignores_chatter_and_quoted_text(self):
        self.assertEqual(g.parse("Thanks!\n\nOn Mon, Oct 26 LaBeau wrote:\n> strike 1"), [])


class GateFlowTests(Base):
    def test_intake_reads_every_line_verbatim(self):
        self.assertEqual(g.intake(self.cfg, reader=lambda p: PAGE), 4)
        r = self.rows()
        self.assertEqual([x["line"] for x in r], [t for t, _ in PAGE])
        self.assertEqual([x["status"] for x in r], ["pending", "held-name", "held-reading", "held-name"])
        self.assertEqual(r[3]["role_options"].split(" | ")[:2], ["my sister", "my big sister"])
        self.assertEqual(r[0]["shared_line"], PAGE[0][0])
        self.assertEqual(r[1]["shared_line"], "")
        self.assertEqual(list((self.tmp / "Voice Inbox").iterdir()), [])
        self.assertEqual(len(list((self.tmp / "Journal Pages").iterdir())), 1)
        # The same photo is never read twice.
        self.assertEqual(g.intake(self.cfg, reader=lambda p: PAGE), 0)
        log = (g.STATE / "gate.log").read_text()
        self.assertNotIn("river", log)
        self.assertNotIn("Marcus", log)

    def test_docket_only_on_monday_morning(self):
        g.run(self.cfg, now=dt.datetime(2026, 10, 25, 23, 0), reader=lambda p: PAGE, replies=[], mailer=self.mailer)
        self.assertEqual(self.sent, [])
        self.monday()
        self.assertEqual(len(self.sent), 1)
        subject, body = self.sent[0]
        self.assertEqual(subject, "LaBeau docket 2026-10-26")
        self.assertIn('2. "I called Marcus after the meeting"', body.replace("1. \"I called", "2. \"I called"))
        self.assertIn("a) my sister  b) my big sister", body)
        self.assertIn("READING UNSURE", body)
        self.assertIn("7 am Tuesday", body)
        # Sending twice the same Monday does not happen.
        g.run(self.cfg, now=MONDAY.replace(hour=12), reader=lambda p: [], replies=[], mailer=self.mailer)
        self.assertEqual(len(self.sent), 1)

    def test_silence_clears_plain_lines_only(self):
        self.monday()
        g.run(self.cfg, now=dt.datetime(2026, 10, 27, 7, 0), reader=lambda p: [], replies=[], mailer=self.mailer)
        status = {x["line"]: x["status"] for x in self.rows()}
        self.assertEqual(status[PAGE[0][0]], "cleared")
        self.assertEqual(status[PAGE[1][0]], "held-name")
        self.assertEqual(status[PAGE[2][0]], "held-reading")

    def test_reply_applies_choices(self):
        self.monday()
        mapping = json.loads((g.STATE / "docket-2026-10-26.json").read_text())
        no = {sl.load(Path(self.cfg["share_library"]))[[r["id"] for r in self.rows()].index(i)]["line"]: n
              for n, i in mapping.items()}
        reply = (f"{no[PAGE[1][0]]} a\n{no[PAGE[3][0]]}: my sister\n"
                 f"{no[PAGE[2][0]]} fix: we were never lost, only early\nstrike {no[PAGE[0][0]]}\n\n"
                 "On Mon, Oct 26, 2026 LaBeau wrote:\n> strike 1")
        g.run(self.cfg, now=MONDAY.replace(hour=12), reader=lambda p: [],
              replies=[("<m1>", "2026-10-26", reply)], mailer=self.mailer)
        shared = {x["line"]: (x["status"], x["shared_line"]) for x in self.rows()}
        self.assertEqual(shared[PAGE[1][0]], ("cleared", "I called a friend after the meeting"))
        self.assertEqual(shared[PAGE[3][0]], ("cleared", "my sister said the porch light stays on"))
        self.assertEqual(shared[PAGE[2][0]], ("cleared", "we were never lost, only early"))
        self.assertEqual(shared[PAGE[0][0]], ("struck", ""))
        cleared = (self.tmp / "sc/cleared.csv").read_text()
        self.assertIn("I called a friend after the meeting", cleared)
        self.assertNotIn("Marcus", cleared)
        self.assertNotIn("tasha", cleared)
        self.assertNotIn("apologize", cleared)  # struck
        self.assertNotIn("nevr", cleared)
        self.assertTrue(self.sent[-1][0].endswith(": done"))
        # The same reply is never applied twice.
        n = len(self.sent)
        g.run(self.cfg, now=MONDAY.replace(hour=19), reader=lambda p: [],
              replies=[("<m1>", "2026-10-26", reply)], mailer=self.mailer)
        self.assertEqual(len(self.sent), n)

    def test_ok_keeps_the_name_and_lens_moves_a_line(self):
        self.monday()
        mapping = json.loads((g.STATE / "docket-2026-10-26.json").read_text())
        ids = {r["id"]: r["line"] for r in self.rows()}
        no = {ids[i]: n for n, i in mapping.items()}
        g.run(self.cfg, now=MONDAY.replace(hour=12), reader=lambda p: [], mailer=self.mailer,
              replies=[("<m2>", "2026-10-26", f"ok {no[PAGE[1][0]]}\nlens {no[PAGE[0][0]]}")])
        shared = {x["line"]: (x["status"], x["shared_line"]) for x in self.rows()}
        self.assertEqual(shared[PAGE[1][0]], ("cleared", PAGE[1][0]))
        self.assertEqual(shared[PAGE[0][0]][0], "lens")
        self.assertIn("): the river does not apologize for the stone\n<!-- harvest adds Chris's",
                      Path(self.cfg["lens_file"]).read_text())

    def test_held_lines_return_on_next_docket(self):
        self.monday()
        g.run(self.cfg, now=MONDAY + dt.timedelta(days=7), reader=lambda p: [], replies=[], mailer=self.mailer)
        body = self.sent[-1][1]
        self.assertIn("Marcus", body)
        self.assertNotIn("CLEARS (silence", body)

    def test_reply_parsing_from_real_email(self):
        msg = email.message.EmailMessage()
        msg["From"], msg["Subject"] = "Chris <cmcald1018@gmail.com>", "Re: LaBeau docket 2026-10-26"
        msg["Message-ID"] = "<abc@mail>"
        msg.set_content("strike 2\n\nOn Mon wrote:\n> x")

        class FakeImap:
            def select(self, *a, **k): return "OK", [b"1"]
            def search(self, *a): return "OK", [b"1"]
            def fetch(self, *a): return "OK", [(b"1", bytes(msg))]

        got = g.fetch_replies(dt.date(2026, 10, 20), imap=FakeImap())
        self.assertEqual(got[0][:2], ("<abc@mail>", "2026-10-26"))
        self.assertEqual(g.parse(got[0][2]), [("strike", "2", "")])
        msg.replace_header("From", "someone@else.com")
        self.assertEqual(g.fetch_replies(dt.date(2026, 10, 20), imap=FakeImap()), [])


class ShareTriggerTests(Base):
    def test_share_memo_joins_the_docket(self):
        inbox = self.tmp / "Voice Inbox"
        (inbox / "share.txt").write_text("Share LaBeau: we were never lost, only early")
        old = time.time() - 60
        os.utime(inbox / "share.txt", (old, old))
        vv.run(self.cfg)
        r = self.rows()
        self.assertEqual([(x["brand"], x["line"], x["status"]) for x in r],
                         [("labeau", "we were never lost, only early", "pending")])
        # voice-vault leaves photos for the gate.
        self.assertTrue((inbox / "IMG_0001.png").exists())

    def test_share_trigger_routes(self):
        self.assertEqual(vv.route("Share. we were never lost", WORDS)[:2], ("share-both", "we were never lost"))
        self.assertEqual(vv.route("Share Chris - red stems", WORDS)[:2], ("share-chris", "red stems"))
        self.assertEqual(vv.route("Share my therapist said", WORDS)[0], "vault")


class LibraryTests(unittest.TestCase):
    def test_ei_weeks(self):
        self.assertEqual(sl.ei_week(dt.date(2026, 10, 24)), "setup")
        self.assertEqual(sl.ei_week(dt.date(2026, 10, 26)), "week 1")
        self.assertEqual(sl.ei_week(dt.date(2026, 12, 20)), "week 8")
        self.assertEqual(sl.ei_week(dt.date(2026, 12, 21)), "after")

    def test_lens_template_passes_privacy_check(self):
        self.assertEqual(vv.private_reasons((HERE / "templates/hierophant-lens.md").read_text(), WORDS), [])


if __name__ == "__main__":
    unittest.main()
