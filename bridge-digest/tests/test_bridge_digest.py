import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bridge_digest as bd  # noqa: E402

MSG = """---
id: {id}
type: {type}
from: grok
to: claude
created_et: {created} 09:00 ET
topic: {topic}
status: {status}
needs_chris: {needs}
---
SECRET BODY TEXT that must never reach the vault.
"""


class DigestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.bridge = os.path.join(root, "grok-bridge")
        self.vault = os.path.join(root, "vault")
        os.makedirs(os.path.join(self.bridge, "to-claude"))
        os.makedirs(os.path.join(self.bridge, "to-hermes"))
        os.makedirs(os.path.join(self.bridge, "status"))
        os.makedirs(os.path.join(self.vault, "Second Brain", "Meta"))
        self.put("to-claude/G2C-2026-10-24-001-private-slug-words.md", MSG.format(
            id="G2C-2026-10-24-001", type="request", created="2026-10-24", topic="personal-ai-risk-framework",
            status="new", needs="yes - a private reason"))
        self.put("to-claude/G2C-2026-10-23-002-other.md", MSG.format(
            id="G2C-2026-10-23-002", type="ack", created="2026-10-23", topic="bridge", status="acked", needs="no"))
        self.put("to-hermes/C2H-2026-10-14-001-old.md", MSG.format(
            id="C2H-2026-10-14-001", type="request", created="2026-10-14", topic="harness", status="new", needs="no"))
        self.put("to-claude/MOVED-G2C-2026-10-21-x.md", "moved")
        self.put("to-claude/G2C-2026-10-22-003-v1-recap.md", "# G2C-2026-10-22-003 recap\nbody\n\n## Status log\n- 2026-10-24 01:51 ET | acked: read.\n")
        self.put("status/claude.json", json.dumps({"agent": "claude-code", "last_session_et": "2026-10-24 01:43 ET",
                                                   "airtable": "ok", "note": "PRIVATE NOTE"}))
        self.put("status/hermes.json", json.dumps({"last_session_et": "2026-10-14 22:25 ET", "airtable": "not connected"}))
        with open(os.path.join(self.vault, "Second Brain", "Meta", "Status Board.md"), "w") as f:
            f.write("---\ntype: status-board\ncreated: 2026-10-16\nday: 125\n---\n")
        self.cfg = dict(bd.DEFAULTS, bridge=self.bridge, vault=self.vault)
        self.now = dt.datetime(2026, 10, 24, 21, 45)
        self.notes = bd.build(self.cfg, self.now.date(), self.now)
        self.digest = self.notes["Bridge Digest - 2026-10-24.md"]
        self.roster = self.notes["Agents - Bridge Roster (Living).md"]

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, rel, text):
        with open(os.path.join(self.bridge, rel), "w") as f:
            f.write(text)

    def test_only_safe_fields_reach_the_vault(self):
        both = self.digest + self.roster
        for leak in ("SECRET BODY", "private-slug", "personal-ai-risk", "a private reason", "PRIVATE NOTE"):
            self.assertNotIn(leak, both)
        self.assertIn("| G2C-2026-10-24-001 | Grok Bot → Claude Code | request | other | new | yes |", self.digest)

    def test_counts_waiting_and_stale(self):
        self.assertIn("open: 4\nnew: 2\nneeds_chris: 1\nstale: 1\n", self.digest)
        self.assertIn("G2C-2026-10-24-001 These go in his Saturday packet", self.digest)
        self.assertIn("## Unacked over 7 days\nC2H-2026-10-14-001", self.digest)
        self.assertNotIn("MOVED", self.digest)

    def test_health_and_day_count(self):
        self.assertIn("| Claude Code | OK | 2026-10-24 01:43 ET | 0 | 1 | ok |", self.roster)
        self.assertIn("| Hermes | Stale | 2026-10-14 22:25 ET | 9 | 1 | not connected |", self.roster)
        self.assertIn("| Muse | No heartbeat | none |  | 0 | unknown |", self.roster)
        self.assertIn("day: 133\n", self.digest)
        self.assertIn("Saturday, October 24, 2026, Day 133", self.digest)
        self.assertIn("```dataview", self.roster)

    def test_writes_only_the_two_notes_and_reruns_in_place(self):
        bd.write(self.cfg, self.notes)
        bd.write(self.cfg, self.notes)
        out = os.path.join(self.vault, "Second Brain", "Meta", "Bridge")
        self.assertEqual(sorted(os.listdir(out)), ["Agents - Bridge Roster (Living).md", "Bridge Digest - 2026-10-24.md"])
        with self.assertRaises(SystemExit):
            bd.write(self.cfg, {"../escape.md": "x"})

    def test_print_writes_nothing(self):
        cfg_path = os.path.join(self.tmp.name, "config.json")
        with open(cfg_path, "w") as f:
            json.dump({"bridge": self.bridge, "vault": self.vault}, f)
        with open(os.devnull, "w") as null:
            stdout, sys.stdout = sys.stdout, null
            try:
                self.assertEqual(bd.main(["--print", "--config", cfg_path, "--date", "2026-10-24"]), 0)
            finally:
                sys.stdout = stdout
        self.assertFalse(os.path.exists(os.path.join(self.vault, "Second Brain", "Meta", "Bridge")))


if __name__ == "__main__":
    unittest.main()
