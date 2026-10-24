import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CLAUDE_MD = """# labeau-ops, project instructions

**Hierophant Lens and journal lines (Oct 23, 2026, his ruling; diary-to-brand pathway v2):** read the Lens.

## Before and after any change
- Run doctor.
"""


class WireStrategyLens(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.ops, self.bridge = self.tmp / "ops", self.tmp / "bridge"
        self.ops.mkdir()
        (self.ops / "CLAUDE.md").write_text(CLAUDE_MD)
        for d in ("to-grok", "to-muse", "threads"):
            (self.bridge / d).mkdir(parents=True)
        (self.bridge / "threads" / "labeau.md").write_text("# LaBeau\n")
        self.glob = self.tmp / "global-CLAUDE.md"
        self.glob.write_text("# global\n")

    def run_wire(self):
        env = dict(os.environ, OPS=str(self.ops), BRIDGE=str(self.bridge), GLOBAL=str(self.glob))
        return subprocess.run([str(HERE / "wire-strategy-lens.sh")], env=env, check=True,
                              capture_output=True, text=True).stdout

    def test_wires_once_beside_hierophant(self):
        self.run_wire()
        out = self.run_wire()
        s = (self.ops / "CLAUDE.md").read_text()
        self.assertEqual(s.count("**Strategy Lens (Oct 24, 2026"), 1)
        self.assertLess(s.index("**Hierophant Lens"), s.index("**Strategy Lens"))
        self.assertLess(s.index("**Strategy Lens"), s.index("## Before and after any change"))
        self.assertIn('"Lens: [framework]. Answers: ... . Decision: one yes/no for Chris."', s)
        lens = (self.ops / "data" / "strategy-lens" / "strategy-lens.md").read_text()
        self.assertIn("10. Portfolio of Initiatives", lens)
        self.assertIn("Source: Natan Mohart's McKinsey frameworks carousel", lens)
        g = self.glob.read_text()
        self.assertEqual(g.count("**Strategy Lens (Oct 24, 2026"), 1)
        self.assertIn("~/Developer/labeau-ops/data/strategy-lens/strategy-lens.md", g)
        self.assertEqual(len(list(self.tmp.glob("CLAUDE.md.bak-*-strategy"))), 1)
        for box in ("to-grok", "to-muse"):
            notes = list((self.bridge / box).glob("*-strategy-lens.md"))
            self.assertEqual(len(notes), 1)
            self.assertNotIn("ROLE_LINE", notes[0].read_text())
        self.assertEqual((self.bridge / "threads" / "labeau.md").read_text().count("Strategy Lens wired"), 1)
        self.assertIn("already has the Strategy Lens", out)

    def test_missing_global_is_skipped(self):
        self.glob.unlink()
        self.assertIn("not found, skipped", self.run_wire())


if __name__ == "__main__":
    unittest.main()
