"""python3 test_hook_first.py [LABEAU_OPS_DIR]: unit checks for the hook-first patch (Oct 24, 2026). Stubs the Mac-only modules."""
import os, sys, types, unittest
OPS = os.path.expanduser(sys.argv.pop(1) if len(sys.argv) > 1 else "~/Developer/labeau-ops")
sys.path.insert(0, OPS)
CFG = {"motion": {}}
if "common" not in sys.modules:
    try:
        import common  # the real one on the Mac
    except Exception:
        sys.modules["common"] = types.SimpleNamespace(HERE=OPS, assets=lambda *a: OPS, CFG=CFG)
        sys.modules["render_preview"] = types.SimpleNamespace(approved_fragment=None, sha256_file=None, slugify=None, probe=None, frames=None, PreviewError=Exception)
        sys.modules["brand_tokens"] = types.SimpleNamespace(css=lambda c: "#000", INK_RGB=(0, 0, 0), CREAM_RGB=(1, 1, 1))
import render_motion as RM

LINES = ["Let someone into all that darkness", "They're bound to bring in a little light", "a third line"]

class HookFirst(unittest.TestCase):
    def test_first_stanza_capped_at_two(self):
        self.assertEqual(RM.hook_lines("breath", LINES)[0], 2)
        self.assertEqual(RM.hook_lines("breath", LINES, (1,))[0], 1)
        self.assertEqual(RM.hook_lines("bloom", LINES[:1])[0], 1)
    def test_kinetic_hook_is_its_first_line(self):
        self.assertEqual(RM.hook_lines("kinetic", LINES), (1, 1.0))
    def test_off_switch(self):
        os.environ["LABEAU_HOOK_FIRST"] = "0"
        try: self.assertEqual(RM.hook_lines("breath", LINES), (0, 0.0))
        finally: del os.environ["LABEAU_HOOK_FIRST"]
    def test_reveal_counts_the_hook(self):
        n, share = RM.hook_lines("breath", LINES)
        t = {"total": 10.2, "settle": 6.2, "hook_share": share}
        def run(early, final):
            orig = RM.text_pixels
            RM.text_pixels = lambda p, at, dark=False, cut=None: early if at < 1 else final
            try: return RM.reveal_check("x.mp4", t)["ok"]
            finally: RM.text_pixels = orig
        self.assertTrue(run(int(share * 1000), 1000))      # the hook is up at 0.25 s: pass
        self.assertFalse(run(0, 1000))                     # an empty first frame: the skip defect, fail
        self.assertFalse(run(1000, 1000))                  # every line up at once: the Oct 9 defect, fail
        t["hook_share"] = 0
        self.assertTrue(run(0, 1000)); self.assertFalse(run(400, 1000))   # off: the old rule

if __name__ == "__main__":
    unittest.main(verbosity=1)
