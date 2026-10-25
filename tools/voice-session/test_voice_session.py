"""Voice session (Oct 24, 2026): finding his takes, cutting between lines, placing lines on screen. Synthetic only."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_session as V

LINES = ["My health is leaving", "And I'm stuck in this rut", "If I stay here longer"]


def heard_of(text, t0=0.0, step=0.4):
    return [(w, t0 + i * step, t0 + i * step + 0.3) for i, w in enumerate(V.words(text))]


class Takes(unittest.TestCase):
    def test_the_retake_wins_over_the_stumble(self):
        pw = [w for l in LINES for w in V.words(l)]
        heard = heard_of("my health is and im stuck uh sorry", 0) + heard_of(" ".join(LINES), 10)
        t = V.choose_take(V.takes_of(pw, heard))
        self.assertEqual(heard[t[1]][1], 10.0)
        self.assertEqual(t[0], 1.0)

    def test_two_clean_takes_the_last_one_wins(self):
        pw = [w for l in LINES for w in V.words(l)]
        heard = heard_of(" ".join(LINES), 0) + heard_of(" ".join(LINES), 20)
        t = V.choose_take(V.takes_of(pw, heard))
        self.assertEqual(heard[t[1]][1], 20.0)

    def test_a_recognizer_misspelling_still_counts(self):
        pw = [w for l in LINES for w in V.words(l)]
        heard = heard_of("my health is leaving and im stuck in this rot if i stay here longer")
        t = V.choose_take(V.takes_of(pw, heard))
        self.assertGreaterEqual(t[0], 0.9)

    def test_a_passage_he_did_not_read_is_missing(self):
        pw = V.words("Peace and blessings War and stressings")
        self.assertIsNone(V.choose_take(V.takes_of(pw, heard_of(" ".join(LINES)))))

    def test_line_spans_follow_the_mapping(self):
        pw = [w for l in LINES for w in V.words(l)]
        heard = heard_of(" ".join(LINES))
        t = V.choose_take(V.takes_of(pw, heard))
        spans = V.line_spans(LINES, t[3], heard)
        self.assertEqual(spans[0][0], 0.0)
        self.assertAlmostEqual(spans[1][0], 0.4 * 4)

    def test_an_unrecognized_first_word_still_starts_the_clip(self):
        pw = [w for l in LINES for w in V.words(l)]
        heard = heard_of("mi health is leaving and im stuck in this rut if i stay here longer", 5.0)
        t = V.choose_take(V.takes_of(pw, heard))
        spans = V.line_spans(LINES, t[3], heard)
        self.assertLessEqual(spans[0][0], 5.0)


class Cuts(unittest.TestCase):
    def test_cut_lands_in_the_breath_between_lines(self):
        spans = [(0.5, 2.0), (3.0, 4.5)]
        db = [-20.0] * 600
        for i in range(210, 290):
            db[i] = -80.0          # silence 2.1 to 2.9 s
        sil = V.silences(db)
        cuts = V.cut_points(spans, db, sil, 6.0)
        self.assertAlmostEqual(cuts[0][1], 2.5, places=1)
        self.assertEqual(cuts[0][1], cuts[1][0])
        self.assertLessEqual(cuts[0][0], 0.5)
        self.assertGreaterEqual(cuts[1][1], 4.5)

    def test_words_said_between_lines_are_dropped(self):
        spans = [(0.5, 2.0), (4.0, 5.5)]
        db = [-20.0] * 700
        for i in list(range(205, 260)) + list(range(330, 395)):
            db[i] = -80.0          # pause, "damn" 2.6 to 3.3 s, pause
        cuts = V.cut_points(spans, db, V.silences(db), 7.0)
        self.assertLess(cuts[0][1], 2.65)
        self.assertGreater(cuts[1][0], 3.3)

    def test_lines_read_in_one_breath_are_joined(self):
        db = [-20.0] * 700
        for i in list(range(0, 45)) + list(range(410, 450)) + list(range(610, 700)):
            db[i] = -80.0          # room tone at the ends, a breath only between lines 2 and 3
        self.assertEqual(V.joined([(0.5, 2.0), (2.02, 4.0), (4.6, 6.0)], V.silences(db)), [True, False])

    def test_a_joined_run_is_used_only_when_the_post_shows_every_line(self):
        takes = {"P": {"lines": [{"clip": "a"}, {"clip": "b"}, {"clip": "c"}], "runs": [{"lines": [0, 1], "clip": "ab"}]}}
        self.assertEqual(V.units([("P", 0, ""), ("P", 1, ""), ("P", 2, "")], takes), (["ab", "c"], [[0, 1], [2]]))
        self.assertEqual(V.units([("P", 1, ""), ("P", 2, "")], takes), (["b", "c"], [[0], [1]]))


class Placement(unittest.TestCase):
    def test_no_line_before_it_is_on_screen(self):
        starts, hold, late = V.place([0.0, 3.0, 6.0], [30, 30, 30], [1.5, 1.5, 1.5], 30.0)
        self.assertLessEqual(starts[0], 1.0)
        self.assertGreaterEqual(starts[1], 3.0)
        self.assertGreaterEqual(starts[2], 6.0)
        self.assertEqual(hold, 0.0)

    def test_a_slow_read_never_overlaps_and_holds_the_last_frame(self):
        starts, hold, late = V.place([0.5, 1.0], [10, 10], [6.0, 6.0], 10.0)
        self.assertGreaterEqual(starts[1], starts[0] + 6.0)
        self.assertGreater(hold, 0)

    def test_kinetic_exit_is_flagged(self):
        starts, hold, late = V.place([0.5, 2.0], [1.5, 3.0], [4.0, 1.0], 20.0)
        self.assertEqual(late, [1])

    def test_unread_onset_falls_back_to_his_pace(self):
        starts, _, _ = V.place([0.5, None], [None, None], [1.0, 1.0], 20.0)
        self.assertAlmostEqual(starts[1], 0.5 + 1.0 + 0.3, places=2)


class Screen(unittest.TestCase):
    def test_visible_by_first_word_or_half(self):
        vis = V.visible(LINES, V.words("My health is leaving And"))
        self.assertEqual(vis, [True, True, False])

    def test_a_lone_short_word_is_not_a_line(self):
        vis = V.visible(["I statement frames"], ["i"])
        self.assertEqual(vis, [False])

    def test_onsets_stay_in_reading_order(self):
        on, off = V.settle([[1.0, 2.0], [0.0, 3.0, 4.0], [5.0]])
        self.assertEqual(on, [1.0, 3.0, 5.0])


class Plan(unittest.TestCase):
    def test_stale_words_are_caught(self):
        plan = {"passages": [{"id": "S1-01", "lines": ["Let someone into all that darkness"], "fragments": {"X": [0, 0]}}]}
        self.assertEqual(V.stale_fragments(plan, {"X": {"text": "Let someone into all that darkness"}}), {})
        self.assertIn("X", V.stale_fragments(plan, {"X": {"text": "Let someone into the darkness"}}))

    def test_stage_records_the_voiced_file_in_the_ledger(self):
        try:
            import asset_ledger as AL
        except ImportError:
            self.skipTest("asset_ledger not beside this script")
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f, led = os.path.join(d, "px-2026-10-26-1__ig_9x16.mp4"), os.path.join(d, "ledger.jsonl")
            open(f, "wb").write(b"silent")
            AL.Ledger(led).add(f, "px-2026-10-26-1__ig_9x16")
            open(f, "wb").write(b"voiced")
            self.assertEqual(V.record([f], led), 1)
            version, info = AL.Ledger(led)._current("px-2026-10-26-1__ig_9x16")
            self.assertEqual(version, AL.hash_file(f))
            n = len(open(led).readlines())
            self.assertEqual(V.record([f], led), 1)  # a re-run counts the same bytes as recorded
            self.assertEqual(len(open(led).readlines()), n)  # and adds no entry


if __name__ == "__main__":
    unittest.main()
