import json
import os
import tempfile
import unittest

from eval_harness import (
    GoldenError, HitConfig, Query, Span, bootstrap_ci, compare_runs, dedup,
    evaluate_run, golden_warnings, hit_at, is_hit, lexical_overlap, load_golden,
    mcnemar_exact, recall_at, rr_at, wilson,
)

SEEK = HitConfig("seek")          # lead 20s, lands before gt midpoint
OVERLAP = HitConfig("overlap")    # >= min(50% of gt, 30s)


def S(start, end, vid="v1"):
    return Span(vid, start, end)


def Q(qid="q1", rel=None, qtype="conceptual", split="dev", text="x"):
    return Query(qid, text, qtype, split, tuple(rel or [S(100, 200)]))


class HitDefinition(unittest.TestCase):
    def test_seek_boundaries(self):
        gt = S(100, 200)                      # window: 80 .. 150
        self.assertTrue(is_hit(S(85, 160), gt, SEEK))     # 15s early is fine
        self.assertTrue(is_hit(S(80, 150), gt, SEEK))     # exactly at lead limit
        self.assertFalse(is_hit(S(70, 145), gt, SEEK))    # 30s early: user sits through lead-in
        self.assertTrue(is_hit(S(150, 220), gt, SEEK))    # at midpoint
        self.assertFalse(is_hit(S(151, 220), gt, SEEK))   # most of the answer already gone

    def test_overlap_cap_and_fraction(self):
        long_gt = S(100, 400)                 # need min(150, 30) = 30s
        self.assertTrue(is_hit(S(50, 140), long_gt, OVERLAP))    # 40s overlap
        self.assertFalse(is_hit(S(50, 120), long_gt, OVERLAP))   # 20s overlap
        short_gt = S(100, 120)                # need min(10, 30) = 10s
        self.assertTrue(is_hit(S(110, 180), short_gt, OVERLAP))
        self.assertFalse(is_hit(S(111, 180), short_gt, OVERLAP))

    def test_wrong_video_never_hits(self):
        self.assertFalse(is_hit(S(100, 175, "other"), S(100, 200), SEEK))
        self.assertFalse(is_hit(S(100, 175, "other"), S(100, 200), OVERLAP))

    def test_unknown_definition(self):
        with self.assertRaises(ValueError):
            is_hit(S(0, 10), S(0, 10), HitConfig("nope"))


class Dedup(unittest.TestCase):
    def test_adjacent_sliding_windows_collapse(self):
        r = [S(0, 75), S(30, 105), S(60, 135)]   # stride 30 over 75s windows
        kept = dedup(r, 0.5)
        self.assertEqual(kept, [S(0, 75), S(60, 135)])  # 30-105 overlaps 45/75 = 60%

    def test_keeps_best_ranked_of_a_cluster(self):
        r = [S(30, 105), S(0, 75)]
        self.assertEqual(dedup(r, 0.5), [S(30, 105)])

    def test_disabled_and_cross_video(self):
        r = [S(0, 75), S(10, 85)]
        self.assertEqual(dedup(r, 0), r)
        self.assertEqual(len(dedup([S(0, 75, "a"), S(0, 75, "b")], 0.5)), 2)

    def test_rank_improves_after_dedup(self):
        q = Q(rel=[S(200, 260)])
        raw = [S(0, 75), S(30, 105), S(200, 275)]   # hit sits at raw rank 3
        with_dd = evaluate_run([q], {"q1": raw}, SEEK, 5, 0.5)["q1"]
        no_dd = evaluate_run([q], {"q1": raw}, SEEK, 5, 0)["q1"]
        self.assertEqual(no_dd.first_rank, 3)
        self.assertEqual(with_dd.first_rank, 2)


class Metrics(unittest.TestCase):
    def test_rank_rr_and_cutoffs(self):
        q = Q(rel=[S(500, 600)])
        s = evaluate_run([q], {"q1": [S(0, 75), S(200, 275), S(500, 575)]}, SEEK, 5, 0.5)["q1"]
        self.assertEqual(s.first_rank, 3)
        self.assertFalse(hit_at(s, 2))
        self.assertTrue(hit_at(s, 3))
        self.assertAlmostEqual(rr_at(s, 5), 1 / 3)
        self.assertEqual(rr_at(s, 2), 0.0)

    def test_multi_span_recall(self):
        q = Q(rel=[S(100, 200), S(900, 1000)])
        s = evaluate_run([q], {"q1": [S(95, 170), S(5000, 5075), S(900, 975)]}, SEEK, 5, 0.5)["q1"]
        self.assertEqual(s.span_ranks, (1, 3))
        self.assertAlmostEqual(recall_at(s, 1), 0.5)
        self.assertAlmostEqual(recall_at(s, 3), 1.0)

    def test_missing_run_counts_as_miss(self):
        s = evaluate_run([Q()], {}, SEEK, 5, 0.5)["q1"]
        self.assertIsNone(s.first_rank)
        self.assertEqual(rr_at(s, 5), 0.0)

    def test_start_error(self):
        s = evaluate_run([Q(rel=[S(100, 200)])], {"q1": [S(88, 160)]}, SEEK, 5, 0.5)["q1"]
        self.assertAlmostEqual(s.start_error_sec, 12.0)


class Stats(unittest.TestCase):
    def test_wilson_known_values(self):
        lo, hi = wilson(9, 10)
        self.assertAlmostEqual(lo, 0.596, places=2)
        self.assertAlmostEqual(hi, 0.982, places=2)
        self.assertEqual(wilson(0, 0), (0.0, 0.0))

    def test_mcnemar(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertEqual(mcnemar_exact(1, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact(8, 0), 2 / 256)
        self.assertAlmostEqual(mcnemar_exact(10, 2), 2 * 79 / 4096)

    def test_bootstrap_is_deterministic_and_brackets_mean(self):
        vals = [1, 0, 1, 1, 0, 1, 0, 1, 1, 1]
        a, b = bootstrap_ci(vals, 500, seed=1), bootstrap_ci(vals, 500, seed=1)
        self.assertEqual(a, b)
        self.assertLessEqual(a[0], 0.7)
        self.assertGreaterEqual(a[1], 0.7)

    def test_paired_comparison_counts(self):
        qs = [Q("a", [S(100, 200)]), Q("b", [S(100, 200)]), Q("c", [S(100, 200)])]
        good, bad = [S(100, 175)], [S(900, 975)]
        ra = {"a": good, "b": good, "c": bad}
        rb = {"a": good, "b": bad, "c": bad}
        sa = evaluate_run(qs, ra, SEEK, 3, 0.5)
        sb = evaluate_run(qs, rb, SEEK, 3, 0.5)
        c = compare_runs(qs, sa, sb, 3, 200, 0)
        self.assertEqual((c["a_only"], c["b_only"], c["both"], c["neither"]), (["b"], [], 1, 1))


class GoldenValidation(unittest.TestCase):
    def _write(self, data):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(data, f)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def _item(self, qid="q1", **over):
        d = {"id": qid, "query": "what is x", "type": "conceptual", "split": "dev",
             "relevant": [{"video_id": "v1", "start_sec": 10, "end_sec": 90}]}
        d.update(over)
        return d

    def test_valid_file_loads_with_hash(self):
        qs, sha = load_golden(self._write({"queries": [self._item()]}))
        self.assertEqual(len(qs), 1)
        self.assertEqual(len(sha), 64)

    def test_collects_every_error(self):
        path = self._write([self._item("a"), self._item("a"),
                            self._item("b", type="weird", split="train"),
                            self._item("c", relevant=[{"video_id": "v", "start_sec": 10, "end_sec": 12}]),
                            self._item("d", relevant=[])])
        with self.assertRaises(GoldenError) as cm:
            load_golden(path)
        text = "\n".join(cm.exception.errors)
        for needle in ("duplicate id", "type 'weird'", "split 'train'", "shorter than", "non-empty list"):
            self.assertIn(needle, text)

    def test_warnings_flag_small_unbalanced_set(self):
        qs = [Q(str(i), qtype="lexical") for i in range(10)]
        w = " | ".join(golden_warnings(qs))
        self.assertIn("only 10 queries", w)
        self.assertIn("not balanced", w)
        self.assertIn("distinct videos", w)
        self.assertIn("no 'test' split", w)


class LexicalAudit(unittest.TestCase):
    def test_overlap_fraction(self):
        transcripts = {"v1": [(0, 10, "unrelated intro"),
                              (100, 150, "we use a hash map to track visited nodes in the list"),
                              (300, 330, "dynamic programming")]}
        q = Query("q", "detect cycle using hash map visited", "lexical", "dev", (S(100, 200),))
        # content tokens: detect, cycle, hash, map, visited -> hash, map, visited present
        self.assertAlmostEqual(lexical_overlap(q, transcripts), 3 / 5)
        self.assertIsNone(lexical_overlap(q, {}))


if __name__ == "__main__":
    unittest.main()
