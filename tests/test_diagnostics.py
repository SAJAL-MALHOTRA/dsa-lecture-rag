import unittest

from diagnostics import (
    SegmentIndex, classify, first_rank_of, oracle_hit, plain_hits, pool_recall,
    quantile, refined_hits, start_offsets,
)
from eval_harness import HitConfig, Query, Span

SEEK = HitConfig("seek")
OVERLAP = HitConfig("overlap")


def S(start, end, vid="v1"):
    return Span(vid, start, end)


def Q(qid="q1", text="hash map visited set", rel=None):
    return Query(qid, text, "conceptual", "dev", tuple(rel or [S(118, 200)]))


def transcript():
    segs = []
    for t in range(0, 300, 10):
        text = "filler words about other things"
        if t == 120:
            text = "so we use a hash map to mark visited set"
        segs.append((float(t), float(t + 10), text))
    return {"v1": segs}


class Pool(unittest.TestCase):
    def test_pool_ceiling_grows_with_n_and_union_beats_members(self):
        q = Q(rel=[S(500, 600)])
        miss = lambda i: S(10 * i, 10 * i + 75, "other")
        bm25 = [miss(i) for i in range(24)] + [S(500, 575)]          # hit at raw rank 25
        dense = [miss(i) for i in range(11)] + [S(495, 570)] + [miss(20)]   # hit at raw rank 12
        runs = {"bm25": {"q1": bm25}, "dense": {"q1": dense}}
        h10, _ = pool_recall([q], runs, 10, OVERLAP)
        h20, size20 = pool_recall([q], runs, 20, OVERLAP)
        h30, _ = pool_recall([q], runs, 30, OVERLAP)
        self.assertEqual((h10["bm25"], h10["dense"], h10["UNION"]), (0, 0, 0))
        self.assertEqual((h20["bm25"], h20["dense"], h20["UNION"]), (0, 1, 1))
        self.assertEqual((h30["bm25"], h30["dense"], h30["UNION"]), (1, 1, 1))
        self.assertGreater(size20, 20)

    def test_pool_uses_raw_results_not_deduped(self):
        q = Q(rel=[S(100, 200)])
        # the hit overlaps a non-hit ranked above it; dedup would hide it, the pool must not
        run = {"q1": [S(0, 75), S(60, 135)]}
        h, _ = pool_recall([q], {"r": run}, 5, SEEK)
        self.assertEqual(h["r"], 0)   # 60..135 starts 58s early: genuinely not a seek hit
        h, _ = pool_recall([q], {"r": run}, 5, OVERLAP)
        self.assertEqual(h["r"], 1)   # contains >= 30s of the answer


class Offsets(unittest.TestCase):
    def test_classification_and_signed_offsets(self):
        gt = S(100, 200)
        q = Q(rel=[gt])
        self.assertEqual(classify(-40, 100, SEEK), "early")
        self.assertEqual(classify(-20, 100, SEEK), "ok")
        self.assertEqual(classify(50, 100, SEEK), "ok")
        self.assertEqual(classify(51, 100, SEEK), "late")
        for result, want_off, want_cls in [(S(60, 140), -40, "early"),
                                           (S(170, 240), 70, "late"),
                                           (S(95, 170), -5, "ok")]:
            rows = start_offsets([q], {"q1": [result]}, OVERLAP, SEEK, 5, 0.5)
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0][2], rows[0][3]), (want_off, want_cls))

    def test_misses_are_excluded_and_first_hit_is_used(self):
        q = Q(rel=[S(100, 200)])
        run = {"q1": [S(900, 975), S(60, 140), S(95, 170)]}
        rows = start_offsets([q], run, OVERLAP, SEEK, 5, 0.5)
        self.assertEqual(rows[0][1], 2)           # rank of first overlap-hit
        self.assertEqual(start_offsets([q], {"q1": [S(900, 975)]}, OVERLAP, SEEK, 5, 0.5), [])

    def test_quantile(self):
        self.assertEqual(quantile([], 0.5), None)
        self.assertEqual(quantile([1, 2, 3, 4, 5], 0.5), 3)
        self.assertAlmostEqual(quantile([0, 10], 0.25), 2.5)


class Refinement(unittest.TestCase):
    def test_refine_moves_seek_to_best_window_and_fixes_early_chunk(self):
        idx = SegmentIndex(transcript(), window=1)
        chunk = S(60, 135)                         # starts 58s before the answer: seek miss
        q = Q()
        self.assertIsNone(first_rank_of(q, [chunk], SEEK))
        refined = idx.refine(chunk, {"hash", "map", "visited", "set"}, pad=3)
        self.assertEqual(refined, S(117, 135))     # segment at 120 minus 3s pad
        self.assertEqual(first_rank_of(q, [refined], SEEK), 1)

    def test_refine_never_leaves_the_chunk_and_falls_back(self):
        idx = SegmentIndex(transcript(), window=1)
        chunk = S(115, 135)
        self.assertEqual(idx.refine(chunk, {"hash"}, pad=50).start, 115)   # clamped to chunk start
        self.assertEqual(idx.refine(chunk, {"zzzunknown"}, pad=3), chunk)  # no lexical evidence
        self.assertEqual(idx.refine(chunk, set(), pad=3), chunk)           # empty query
        self.assertEqual(idx.refine(S(0, 50, "no_transcript"), {"hash"}, 3), S(0, 50, "no_transcript"))

    def test_window_scoring_prefers_dense_region(self):
        segs = [(float(t), float(t + 10), "filler") for t in range(0, 100, 10)]
        segs[4] = (40.0, 50.0, "hash map")
        segs[5] = (50.0, 60.0, "visited set")
        idx = SegmentIndex({"v1": segs}, window=2)
        out = idx.refine(S(0, 100), {"hash", "map", "visited", "set"}, pad=0)
        self.assertEqual(out.start, 40.0)          # window of 2 starting at the 'hash map' segment

    def test_oracle_is_an_upper_bound_on_refinement(self):
        idx = SegmentIndex(transcript(), window=1)
        q = Q()
        self.assertTrue(oracle_hit(S(60, 135), q, idx, SEEK))    # a segment start (110..120) fits
        self.assertFalse(oracle_hit(S(0, 75), q, idx, SEEK))     # chunk never reaches the answer
        run = {"q1": [S(60, 135)]}
        refined = refined_hits([q], run, idx, 3, SEEK, [1], 5, 0.5)[1]
        plain = plain_hits([q], run, SEEK, [1], 5, 0.5)[1]
        self.assertEqual((plain, refined), (0, 1))


if __name__ == "__main__":
    unittest.main()
