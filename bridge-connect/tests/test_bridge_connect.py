import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge_connect as bc  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "bridge_connect.py"
NOON = datetime(2026, 10, 23, 12, 5, tzinfo=bc.ET)
TOKEN = "t" * 48


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "grok-bridge"
        self.root.mkdir()
        (self.root / "to-grok").mkdir()
        (self.root / "to-grok" / "C2G-2026-10-23-001-secret.md").write_text("---\nstatus: new\n---\nnot for chatgpt\n")
        self.cfg = Path(self.tmp.name) / "config"
        self.cfg.mkdir()
        (self.cfg / "private-names.txt").write_text("# names\nZebulon Quill\n")
        self.old_cfg, bc.CONFIG = bc.CONFIG, self.cfg
        self.b = bc.Bridge("chatgpt", self.root, now=lambda: NOON)

    def tearDown(self):
        bc.CONFIG = self.old_cfg
        self.tmp.cleanup()

    def call(self, name, **args):
        r = bc.handle(self.b, {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": name, "arguments": args}})
        return r["result"]


class SubmitTests(Base):
    def test_submit_writes_protocol_file_in_from_folder_only(self):
        out = self.b.submit_brief("grok", "Weekday brief: Friday", "Three ideas for the Gist post.")
        self.assertEqual(out["id"], "O2G-2026-10-23-001")
        files = list((self.root / "from-chatgpt").glob("*.md"))
        self.assertEqual([f.name for f in files], ["O2G-2026-10-23-001-weekday-brief-friday.md"])
        text = files[0].read_text()
        fm = bc.front(text)
        self.assertEqual((fm["status"], fm["from"], fm["to"], fm["created_et"]), ("new", "chatgpt", "grok", "2026-10-23 12:05 ET"))
        self.assertIn("## Status log", text)
        self.assertEqual(sorted(p.name for p in (self.root / "to-grok").iterdir()), ["C2G-2026-10-23-001-secret.md"])
        self.assertEqual(oct(files[0].stat().st_mode & 0o777), "0o600")

    def test_numbers_count_up_and_duplicates_return_the_first(self):
        a = self.b.submit_brief("grok", "One", "x")
        b = self.b.submit_brief("claude", "Two", "y")
        c = self.b.submit_brief("grok", "One", "x again")
        self.assertEqual((a["id"], b["id"]), ("O2G-2026-10-23-001", "O2C-2026-10-23-002"))
        self.assertTrue(c["duplicate"])
        self.assertEqual(c["id"], a["id"])
        self.assertEqual(len(list((self.root / "from-chatgpt").glob("*.md"))), 2)

    def test_daily_cap(self):
        for i in range(bc.DAILY_CAP):
            self.b.submit_brief("grok", f"Brief {i}", "x")
        with self.assertRaises(bc.ToolError):
            self.b.submit_brief("grok", "One too many", "x")

    def test_privacy_blocks_and_writes_nothing(self):
        for body in ("Ask Zebulon Quill about it", "after my therapy session", "key sk-proj-abcdefghijklmnopqrstuvwx",
                     "see ~/Documents/Desktop/Recovery/notes", "token: abcdefghijklmnop1234"):
            r = self.call("submit_brief", to="grok", title="Plan", body=body)
            self.assertTrue(r["isError"], body)
            self.assertIn("Not sent", r["content"][0]["text"])
            self.assertNotIn("Zebulon", r["content"][0]["text"])
        self.assertEqual(list((self.root / "from-chatgpt").glob("*.md")), [])

    def test_bad_recipient_and_empty(self):
        self.assertTrue(self.call("submit_brief", to="hermes", title="x", body="y")["isError"])
        self.assertTrue(self.call("submit_brief", to="grok", title="", body="y")["isError"])
        self.assertTrue(self.call("submit_brief", to="grok")["isError"])


class ReceiptAndInboxTests(Base):
    def test_receipt_follows_the_recipients_status_line(self):
        fid = self.b.submit_brief("grok", "Receipt test", "x")["id"]
        self.assertEqual(self.b.check_receipt(fid)["receipt"], bc.RECEIPT["new"])
        p = next((self.root / "from-chatgpt").glob(f"{fid}-*.md"))
        p.write_text(p.read_text().replace("status: new", "status: acked") + "- 2026-10-23 12:30 ET | acked | Grok: got it\n")
        r = self.b.check_receipt(fid)
        self.assertEqual(r["status"], "acked")
        self.assertEqual(r["status_log"], ["2026-10-23 12:30 ET | acked | Grok: got it"])

    def test_inbox_read_and_ack(self):
        to = self.root / "to-chatgpt"
        to.mkdir()
        (to / "G2O-2026-10-23-001-hello.md").write_text("---\nid: G2O-2026-10-23-001\ntitle: Hello\nstatus: new\n---\n# Hello\nbody\n")
        (to / "C2O-2026-10-23-002-held.md").write_text("---\nstatus: new\n---\n# Held\nmet Zebulon Quill\n")
        inbox = self.b.list_inbox()["messages"]
        self.assertEqual([(m["id"], m["from"]) for m in inbox], [("C2O-2026-10-23-002", "claude"), ("G2O-2026-10-23-001", "grok")])
        self.assertEqual(inbox[0]["title"], "(held by the privacy check)")
        self.assertIn("body", self.b.read_message("G2O-2026-10-23-001")["text"])
        self.assertTrue(self.call("read_message", id="C2O-2026-10-23-002")["isError"])
        self.b.ack_message("G2O-2026-10-23-001", "done", "answered in O2G-2026-10-23-001")
        text = (to / "G2O-2026-10-23-001-hello.md").read_text()
        self.assertIn("status: done", text)
        self.assertIn("- 2026-10-23 12:05 ET | done | ChatGPT: answered in O2G-2026-10-23-001", text)
        self.assertEqual(self.b.list_inbox()["messages"][0]["id"], "C2O-2026-10-23-002")
        self.assertTrue(self.call("ack_message", id="G2O-2026-10-23-001", status="blocked")["isError"])

    def test_cannot_reach_other_folders(self):
        for bad in ("C2G-2026-10-23-001", "../to-grok/C2G-2026-10-23-001", "C2G-2026-10-23-001-secret.md", "*"):
            self.assertTrue(self.call("read_message", id=bad)["isError"], bad)
            self.assertTrue(self.call("check_receipt", id=bad)["isError"], bad)

    def test_refuses_a_linked_folder(self):
        os.symlink(self.root / "to-grok", self.root / "to-chatgpt")
        self.assertTrue(self.call("list_inbox")["isError"])

    def test_perplexity_uses_its_own_folders(self):
        p = bc.Bridge("perplexity", self.root, now=lambda: NOON)
        self.assertEqual(p.submit_brief("claude", "Sources", "x")["id"], "P2C-2026-10-23-001")
        self.assertTrue((self.root / "from-perplexity").is_dir())
        self.assertFalse((self.root / "from-chatgpt").exists())


class ProtocolTests(Base):
    def test_initialize_and_list(self):
        r = bc.handle(self.b, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-03-26")
        self.assertIsNone(bc.handle(self.b, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
        names = [t["name"] for t in bc.handle(self.b, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
        self.assertEqual(names, ["submit_brief", "check_receipt", "list_inbox", "read_message", "ack_message"])
        self.assertEqual(bc.handle(self.b, {"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"], -32601)

    def test_stdio_end_to_end(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "submit_brief", "arguments": {"to": "grok", "title": "Stdio", "body": "hi"}}},
        ]
        env = dict(os.environ, BRIDGE_ROOT=str(self.root))
        out = subprocess.run([sys.executable, str(SCRIPT), "--agent", "perplexity", "--stdio"], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                             capture_output=True, text=True, env=env, timeout=20)
        lines = [json.loads(l) for l in out.stdout.splitlines()]
        self.assertEqual([l["id"] for l in lines], [1, 2])
        self.assertFalse(lines[1]["result"]["isError"])
        self.assertEqual(len(list((self.root / "from-perplexity").glob("P2G-*.md"))), 1)


class HttpTests(Base):
    def setUp(self):
        super().setUp()
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), bc.make_handler(self.b, TOKEN))
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def post(self, path, body, headers=None):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, (json.loads(r.read() or b"null"))
        except urllib.error.HTTPError as e:
            return e.code, None

    def test_token_in_path_or_header(self):
        call = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        self.assertEqual(self.post(f"/mcp/{TOKEN}", call)[0], 200)
        self.assertEqual(self.post("/mcp", call, {"Authorization": f"Bearer {TOKEN}"})[0], 200)
        self.assertEqual(self.post("/mcp", call)[0], 401)
        self.assertEqual(self.post("/mcp/wrong", call)[0], 401)
        self.assertEqual(self.post(f"/other/{TOKEN}", call)[0], 401)
        self.assertEqual(self.post(f"/mcp/{TOKEN}", {"jsonrpc": "2.0", "method": "notifications/initialized"})[0], 202)

    def test_submit_and_receipt_over_http(self):
        code, r = self.post(f"/mcp/{TOKEN}", {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                              "params": {"name": "submit_brief", "arguments": {"to": "grok", "title": "HTTP", "body": "hi"}}})
        self.assertEqual(code, 200)
        fid = r["result"]["structuredContent"]["id"]
        code, r = self.post(f"/mcp/{TOKEN}", {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                              "params": {"name": "check_receipt", "arguments": {"id": fid}}})
        self.assertEqual(r["result"]["structuredContent"]["status"], "new")


if __name__ == "__main__":
    unittest.main()
