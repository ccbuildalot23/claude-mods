"""Tests for Mission Control against a tiny fake labeau-ops tree.

Run: python3 -m unittest test_mission_control  (from this folder)
"""
import datetime as dt, json, os, subprocess, sys, tempfile, textwrap, unittest

HERE = os.path.dirname(os.path.abspath(__file__))

FAKE_COMMON = textwrap.dedent('''
    import csv, os
    HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA = os.path.join(HERE, "data")
    def read_csv(name):
        with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    def index_by(rows, key):
        return {r[key]: r for r in rows}
    def placement_slot(pl, pls=None):
        sibs = sorted(r["placement_id"] for r in pls if r["date"] == pl["date"] and r["platform"] == pl["platform"])
        return sibs.index(pl["placement_id"]) + 1
    def read_caption(date, platform, slot=1):
        p = os.path.join(DATA, "captions", f"{date}-{platform}-{slot}.txt")
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    def find_assets(slug):
        root = os.path.join(HERE, "posts")
        return sorted(os.path.join(root, f) for f in os.listdir(root) if slug and f.startswith(slug))
''')

FAKE_PREPARE = textwrap.dedent('''
    def packet_for(date):
        if date.isoformat() != "2026-10-23":
            return ""
        return "\\n".join([
            "# Packet",
            "### Instagram  ·  slot 1  ·  READY",
            "- **Files:**",
            "    - `04-posts/a.mp4`",
            "### Tiktok  ·  slot 1  ·  HOLD",
            "- **Files:**",
            "    - `04-posts/b.jpg`",
            "- **Held because:**",
            "    - single still on a video-first platform",
            "## Checklist",
        ])
''')

PLACEMENTS = """placement_id,date,platform,lane,piece_id,fragment_id,asset_slug,music_mode,rights,state,posted_at,post_url,notes
P1,2026-10-23,instagram,manual,C3,,a,original-audio,ok,planned,,,
P2,2026-10-23,tiktok,manual,C3,,b,original-audio,ok,planned,,,
P3,2026-10-24,instagram,manual,C3,,c,original-audio,ok,planned,,,
P4,2026-10-24,tiktok,manual,C3,,zzz,original-audio,ok,cancelled,,,
"""


class MissionControlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        ops = os.path.join(self.tmp, "ops")
        for d in ("scripts", "data/captions", "data/logs", "posts"):
            os.makedirs(os.path.join(ops, d))
        open(os.path.join(ops, "scripts/common.py"), "w").write(FAKE_COMMON)
        open(os.path.join(ops, "scripts/prepare_tomorrow.py"), "w").write(FAKE_PREPARE)
        open(os.path.join(ops, "data/placements.csv"), "w").write(PLACEMENTS)
        cap = os.path.join(ops, "data/captions")
        open(os.path.join(cap, "2026-10-23-instagram-1.txt"), "w").write("A full caption.")
        open(os.path.join(cap, "2026-10-23-tiktok-1.txt"), "w").write("[YOUR WORDS] here")
        for f in ("a.mp4", "b.jpg"):
            open(os.path.join(ops, "posts", f), "w").write("x")
        self.ops = ops
        self.env = dict(os.environ, LABEAU_OPS=ops, MC_STATE=os.path.join(self.tmp, "state"),
                        MC_DRIVE_DIR=os.path.join(self.tmp, "drive"))

    def run_mc(self, now, mail_rows=""):
        open(os.path.join(self.ops, "data/logs/mail_sent.csv"), "w").write("date,sent_at\n" + mail_rows)
        subprocess.run([sys.executable, os.path.join(HERE, "mission_control.py"), "--now", now, "--no-alert"],
                       env=self.env, check=True, capture_output=True)
        s = json.load(open(os.path.join(self.tmp, "drive", "labeau-mission-status.json")))
        return s, {c["id"]: c for c in s["cards"]}

    def test_reds_by_four(self):
        s, c = self.run_mc("2026-10-22T16:05", "2026-10-22,2026-10-21T16:15\n")
        self.assertEqual(c["captions"]["status"], "red")
        self.assertIn("placeholder", " ".join(c["captions"]["details"]))
        self.assertEqual(c["assets"]["status"], "red")
        self.assertIn("single still", " ".join(c["assets"]["details"]))
        self.assertEqual(c["tomorrow"]["status"], "red")
        self.assertIn("single still on a video-first platform", " ".join(c["tomorrow"]["details"]))
        self.assertNotIn("04-posts", " ".join(c["tomorrow"]["details"]))
        self.assertEqual(c["email"]["status"], "green")
        self.assertEqual(s["overall"], "red")

    def test_lookahead_is_yellow_and_cancelled_rows_skipped(self):
        _, c = self.run_mc("2026-10-22T16:05", "2026-10-22,x\n")
        later = [d for d in c["captions"]["details"] if d.startswith("Sat")]
        self.assertEqual(len(later), 1)
        self.assertNotIn("P4", " ".join(c["assets"]["details"]))

    def test_email_states(self):
        _, c = self.run_mc("2026-10-22T16:20", "2026-10-22,x\n")
        self.assertEqual(c["email"]["status"], "yellow")
        _, c = self.run_mc("2026-10-22T16:45", "2026-10-22,x\n")
        self.assertEqual(c["email"]["status"], "red")
        self.assertIn("2026-10-23 --send", c["email"]["fix"])
        _, c = self.run_mc("2026-10-22T16:45", "2026-10-22,x\n2026-10-23,y\n")
        self.assertEqual(c["email"]["status"], "green")
        _, c = self.run_mc("2026-10-22T07:00", "2026-10-22,TEST\n")
        self.assertEqual(c["email"]["status"], "red")
        self.assertIn("2026-10-22 --send", c["email"]["fix"])

    def test_no_send_log_means_not_sent(self):
        log = os.path.join(self.ops, "data/logs/mail_sent.csv")
        if os.path.exists(log):
            os.remove(log)
        subprocess.run([sys.executable, os.path.join(HERE, "mission_control.py"), "--now", "2026-10-22T16:57", "--no-alert"],
                       env=self.env, check=True, capture_output=True)
        s = json.load(open(os.path.join(self.tmp, "drive", "labeau-mission-status.json")))
        c = {x["id"]: x for x in s["cards"]}["email"]
        self.assertEqual(c["status"], "red")
        self.assertIn("2026-10-22 --send", c["fix"])

    def test_captions_log_reads_only_last_run(self):
        log = os.path.join(self.ops, "data/logs/captions-daily.log")
        open(log, "w").write("=== 2026-10-20 21:40 EDT captions-daily\nNot logged in\n=== 2026-10-21 21:40 EDT captions-daily\nok\n")
        _, c = self.run_mc("2026-10-22T12:00", "2026-10-22,x\n")
        self.assertNotIn("Not logged in", " ".join(c["captions"]["details"]))
        open(log, "a").write("=== 2026-10-22 21:40 EDT captions-daily\nNot logged in · Please run /login\n")
        _, c = self.run_mc("2026-10-22T12:00", "2026-10-22,x\n")
        self.assertIn("2026-10-22 21:40", " ".join(c["captions"]["details"]))

    def test_broken_ops_is_red_not_silent(self):
        os.remove(os.path.join(self.ops, "data/placements.csv"))
        _, c = self.run_mc("2026-10-22T12:00", "2026-10-22,x\n")
        self.assertEqual(c["captions"]["status"], "red")
        self.assertIn("couldn't read", c["captions"]["headline"])


class AlertSlotTest(unittest.TestCase):
    def test_slots(self):
        sys.path.insert(0, HERE)
        import mission_control as mc
        log = os.path.join(tempfile.mkdtemp(), "alerts.csv")
        self.assertIsNone(mc.alert_slot_due(dt.datetime(2026, 10, 22, 15, 35), log))
        self.assertEqual(mc.alert_slot_due(dt.datetime(2026, 10, 22, 16, 5), log), "prep")
        self.assertEqual(mc.alert_slot_due(dt.datetime(2026, 10, 22, 16, 35), log), "email")
        open(log, "w").write("2026-10-22,email,x,y,sent\n")
        self.assertIsNone(mc.alert_slot_due(dt.datetime(2026, 10, 22, 17, 5), log))
        self.assertEqual(mc.alert_slot_due(dt.datetime(2026, 10, 23, 6, 35), log), "morning")



class WatchdogTest(unittest.TestCase):
    """Loop-engineering change 1 (Oct 29, 2026): labeau health cannot judge itself, so this card does."""
    def test_never_run_stale_red_and_fresh(self):
        sys.path.insert(0, HERE)
        import mission_control as mc
        p = os.path.join(tempfile.mkdtemp(), "health.json")
        now = dt.datetime(2026, 10, 29, 8, 30)
        self.assertEqual(mc.watchdog_card(now, p)["status"], "red")
        json.dump({"checked_at": "2026-10-27T21:15:00", "overall": "GREEN", "checks": {}}, open(p, "w"))
        self.assertIn("quiet", mc.watchdog_card(now, p)["headline"])
        json.dump({"checked_at": "2026-10-29T06:50:00", "overall": "RED", "red": 1,
                   "checks": {"heartbeats": {"red_lines": ["hermes: 5 days ago"]}}}, open(p, "w"))
        c = mc.watchdog_card(now, p)
        self.assertEqual(c["status"], "yellow")
        self.assertIn("hermes: 5 days ago", c["details"])
        json.dump({"checked_at": "2026-10-29T06:50:00", "overall": "GREEN", "checks": {}}, open(p, "w"))
        self.assertEqual(mc.watchdog_card(now.astimezone(), p)["status"], "green")
        self.assertIn("ink.labeau.pipeline-health", mc.EXPECTED_JOBS)


if __name__ == "__main__":
    unittest.main()
