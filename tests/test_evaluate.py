"""
Tests for the evaluation harness.

Uses a mock retriever to verify that Hit Rate, MRR, Precision,
overlap logic, and the ablation table all work correctly
before any real retrieval code exists.

Run: python -m pytest tests/ -v
"""

from ytrag.models import Chunk, RetrievalResult, GoldenQuery
from ytrag.evaluate import (
    interval_overlap,
    is_hit,
    score_query,
    evaluate,
    ablation_table,
    load_golden_set,
    save_golden_set,
)
from pathlib import Path
import tempfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_chunk(video_id: str, start: int, end: int, text: str = "...") -> Chunk:
    return Chunk(
        chunk_id=f"{video_id}:{start}",
        video_id=video_id,
        video_title="Test Video",
        start_sec=start,
        end_sec=end,
        text=text,
    )


def make_result(video_id: str, start: int, end: int, score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk=make_chunk(video_id, start, end),
        score=score,
        retriever_name="test",
    )


# ---------------------------------------------------------------------------
# Overlap tests
# ---------------------------------------------------------------------------

class TestOverlap:
    def test_full_overlap(self):
        assert interval_overlap("v1", 100, 200, "v1", 100, 200) == 100

    def test_partial_overlap(self):
        assert interval_overlap("v1", 100, 200, "v1", 150, 250) == 50

    def test_no_overlap(self):
        assert interval_overlap("v1", 100, 200, "v1", 300, 400) == 0

    def test_different_videos(self):
        assert interval_overlap("v1", 100, 200, "v2", 100, 200) == 0

    def test_contained(self):
        # chunk is inside ground truth
        assert interval_overlap("v1", 100, 300, "v1", 150, 200) == 50

    def test_touching_boundary(self):
        # intervals [100,200] and [200,300] share the single point 200
        assert interval_overlap("v1", 100, 200, "v1", 200, 300) == 0

    def test_one_second_overlap(self):
        assert interval_overlap("v1", 100, 201, "v1", 200, 300) == 1


# ---------------------------------------------------------------------------
# Hit detection tests
# ---------------------------------------------------------------------------

class TestIsHit:
    def test_hit_with_sufficient_overlap(self):
        r = make_result("v1", 150, 225, 0.9)
        gt = [("v1", 100, 200)]
        assert is_hit(r, gt, overlap_threshold=10) is True

    def test_miss_with_insufficient_overlap(self):
        r = make_result("v1", 195, 270, 0.9)
        gt = [("v1", 100, 200)]
        # overlap is 5 seconds (195-200), below threshold of 10
        assert is_hit(r, gt, overlap_threshold=10) is False

    def test_hit_across_multiple_ground_truths(self):
        r = make_result("v2", 280, 360, 0.8)
        gt = [("v1", 100, 200), ("v2", 270, 400)]
        assert is_hit(r, gt, overlap_threshold=10) is True

    def test_miss_wrong_video(self):
        r = make_result("v1", 100, 200, 0.9)
        gt = [("v2", 100, 200)]
        assert is_hit(r, gt, overlap_threshold=10) is False


# ---------------------------------------------------------------------------
# Per-query scoring
# ---------------------------------------------------------------------------

class TestScoreQuery:
    def test_perfect_retrieval(self):
        """Top-1 result is a hit."""
        query = GoldenQuery(
            query_id="q1", query="test",
            ground_truth_intervals=[("v1", 100, 200)],
        )
        results = [
            make_result("v1", 110, 185, 0.95),  # hit
            make_result("v1", 500, 575, 0.80),   # miss
            make_result("v2", 100, 175, 0.70),   # miss (wrong video)
        ]
        qs = score_query(query, results, k=3)
        assert qs.hit is True
        assert qs.reciprocal_rank == 1.0
        assert qs.precision_at_k > 0.3  # 1 out of 3

    def test_hit_at_rank_2(self):
        """First result misses, second hits."""
        query = GoldenQuery(
            query_id="q2", query="test",
            ground_truth_intervals=[("v1", 100, 200)],
        )
        results = [
            make_result("v1", 500, 575, 0.95),   # miss
            make_result("v1", 120, 195, 0.80),    # hit
            make_result("v1", 800, 875, 0.70),    # miss
        ]
        qs = score_query(query, results, k=3)
        assert qs.hit is True
        assert qs.reciprocal_rank == 0.5  # 1/2
        assert abs(qs.precision_at_k - 1/3) < 0.01

    def test_total_miss(self):
        """No results overlap with ground truth."""
        query = GoldenQuery(
            query_id="q3", query="test",
            ground_truth_intervals=[("v1", 100, 200)],
        )
        results = [
            make_result("v1", 500, 575, 0.95),
            make_result("v2", 100, 175, 0.80),
            make_result("v1", 800, 875, 0.70),
        ]
        qs = score_query(query, results, k=3)
        assert qs.hit is False
        assert qs.reciprocal_rank == 0.0
        assert qs.precision_at_k == 0.0


# ---------------------------------------------------------------------------
# Full evaluation with mock retrievers
# ---------------------------------------------------------------------------

class TestEvaluate:
    def setup_method(self):
        self.queries = [
            GoldenQuery(
                query_id="q1", query="memoization vs tabulation",
                ground_truth_intervals=[("v1", 100, 200)],
                category="dsa", query_type="conceptual",
            ),
            GoldenQuery(
                query_id="q2", query="cycle detection directed graph",
                ground_truth_intervals=[("v2", 300, 450)],
                category="dsa", query_type="conceptual",
            ),
            GoldenQuery(
                query_id="q3", query="O(n log n) sorting",
                ground_truth_intervals=[("v3", 50, 180)],
                category="dsa", query_type="exact_keyword",
            ),
        ]

    def test_perfect_retriever(self):
        """A retriever that always returns the right chunk at rank 1."""
        gt_map = {q.query_id: q for q in self.queries}

        def perfect_retrieve(query_text: str, k: int):
            # cheat: return the ground truth interval as a chunk
            for q in self.queries:
                if q.query == query_text:
                    vid, s, e = q.ground_truth_intervals[0]
                    return [make_result(vid, s, e, 1.0)]
            return []

        report = evaluate(self.queries, perfect_retrieve, "perfect", k=3)
        assert report.hit_rate == 1.0
        assert report.mrr == 1.0

    def test_terrible_retriever(self):
        """A retriever that always returns irrelevant chunks."""
        def bad_retrieve(query_text: str, k: int):
            return [make_result("vX", 9000, 9075, 0.5) for _ in range(k)]

        report = evaluate(self.queries, bad_retrieve, "random", k=3)
        assert report.hit_rate == 0.0
        assert report.mrr == 0.0

    def test_mediocre_retriever(self):
        """Hits on 2 out of 3 queries."""
        def mediocre_retrieve(query_text: str, k: int):
            if "memoization" in query_text:
                return [make_result("v1", 110, 185, 0.9)]    # hit
            elif "cycle" in query_text:
                return [make_result("v2", 320, 420, 0.85)]   # hit
            else:
                return [make_result("vX", 9000, 9075, 0.5)]  # miss
        
        report = evaluate(self.queries, mediocre_retrieve, "mediocre", k=3)
        assert abs(report.hit_rate - 2/3) < 0.01
        assert report.mrr > 0.0


# ---------------------------------------------------------------------------
# Ablation table formatting
# ---------------------------------------------------------------------------

class TestAblationTable:
    def test_table_renders(self):
        """Ablation table produces valid Markdown."""
        from ytrag.evaluate import EvalReport

        reports = [
            EvalReport("bm25", k=3, num_queries=10, hit_rate=0.60, mrr=0.55, mean_precision=0.40),
            EvalReport("dense", k=3, num_queries=10, hit_rate=0.70, mrr=0.65, mean_precision=0.50),
            EvalReport("hybrid", k=3, num_queries=10, hit_rate=0.85, mrr=0.78, mean_precision=0.60),
        ]
        table = ablation_table(reports)
        assert "| Retriever" in table
        assert "hybrid" in table
        assert "85.0%" in table
        # should be sorted by hit_rate descending
        lines = table.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("| ") and "Retriever" not in l and "---" not in l]
        assert "hybrid" in data_lines[0]  # highest hit_rate first


# ---------------------------------------------------------------------------
# Golden set I/O
# ---------------------------------------------------------------------------

class TestGoldenSetIO:
    def test_roundtrip(self):
        """Save and load a golden set, get the same data back."""
        queries = [
            GoldenQuery(
                query_id="q1",
                query="what is backpropagation",
                ground_truth_intervals=[("v1", 100, 200), ("v2", 50, 120)],
                category="ml",
                query_type="conceptual",
                notes="Multiple explanations across lectures",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_golden.json"
            save_golden_set(queries, path)
            loaded = load_golden_set(path)

        assert len(loaded) == 1
        assert loaded[0].query_id == "q1"
        assert loaded[0].query == "what is backpropagation"
        assert len(loaded[0].ground_truth_intervals) == 2
        assert loaded[0].ground_truth_intervals[0] == ("v1", 100, 200)
        assert loaded[0].category == "ml"
