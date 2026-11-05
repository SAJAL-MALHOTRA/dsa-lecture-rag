"""
Unit tests for semantic boundary-aware chunking.

Tests that chunk boundaries snap to speaker pauses, topic transitions,
and sentence completions rather than cutting mid-explanation.
"""

from ytrag.models import Segment
from ytrag.chunk import chunk_segments, find_semantic_boundary


def test_find_semantic_boundary_topic_cue():
    """A topic transition cue ("let's code this") should be the highest-priority boundary."""
    segments = [
        Segment(start=0.0, end=30.0, text="So the brute force approach is O(N^2)."),
        Segment(start=30.5, end=60.0, text="We iterate through each pair of elements."),
        Segment(start=60.5, end=72.0, text="That covers the brute force."),
        Segment(start=74.0, end=100.0, text="Now let's code this optimal approach using two pointers."),
    ]
    # Target boundary around 75s with tolerance 12s
    boundary = find_semantic_boundary(segments, target_sec=75.0, tolerance_sec=12.0)
    # Should snap to 72.0 (end of segment before the topic transition cue)
    assert boundary is not None
    assert boundary == 72.0


def test_find_semantic_boundary_speaker_pause():
    """A long silence gap >= 1.2s should be detected as a natural boundary."""
    segments = [
        Segment(start=0.0, end=30.0, text="We check if the element exists."),
        Segment(start=30.2, end=58.0, text="Using a hash map gives us O(1) lookup."),
        # 2.5s silence gap here
        Segment(start=60.5, end=90.0, text="Moving on to the next problem."),
    ]
    boundary = find_semantic_boundary(segments, target_sec=60.0, tolerance_sec=12.0)
    assert boundary is not None
    assert boundary == 58.0


def test_find_semantic_boundary_sentence_end():
    """Sentence-ending punctuation with moderate pause (>= 0.4s) is a valid boundary."""
    segments = [
        Segment(start=0.0, end=40.0, text="The pointer moves from left to right."),
        # 0.6s gap with sentence-ending period
        Segment(start=40.6, end=70.0, text="Then we compare with the target value"),
        Segment(start=70.2, end=100.0, text="and return the index."),
    ]
    boundary = find_semantic_boundary(segments, target_sec=42.0, tolerance_sec=12.0)
    assert boundary is not None
    assert boundary == 40.0


def test_find_semantic_boundary_none_when_no_candidate():
    """Returns None when no natural boundary exists near the target."""
    segments = [
        Segment(start=0.0, end=10.0, text="start"),
        Segment(start=10.05, end=20.0, text="middle"),  # tiny gap, no punctuation
        Segment(start=20.05, end=30.0, text="end"),      # tiny gap, no punctuation
    ]
    # Target at 50 is way out of all segment boundaries
    boundary = find_semantic_boundary(segments, target_sec=50.0, tolerance_sec=5.0)
    assert boundary is None


def test_semantic_chunking_preserves_invariants():
    """Semantic chunking should still produce valid non-empty, deduplicated chunks."""
    segments = [
        Segment(start=0.0, end=20.0, text="Introduction to binary search."),
        Segment(start=20.5, end=45.0, text="First we check the middle element of the sorted array."),
        Segment(start=47.0, end=72.0, text="If target is smaller, we move left pointer."),
        # 2s pause here: natural boundary
        Segment(start=74.0, end=100.0, text="Now let's code this approach step by step."),
        Segment(start=100.3, end=130.0, text="We initialize low equals zero and high equals n minus one."),
    ]

    chunks = chunk_segments(
        video_id="v_sem",
        video_title="Binary Search Lecture",
        segments=segments,
        window_sec=75,
        overlap_sec=15,
        use_semantic_boundaries=True,
    )

    assert len(chunks) > 0
    # All chunk IDs should be unique
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    # All chunks should have non-empty text
    for c in chunks:
        assert len(c.text.strip()) > 0
        assert c.start_sec < c.end_sec


def test_semantic_chunking_vs_rigid():
    """Semantic chunking should still produce a comparable number of chunks to rigid slicing."""
    segments = [
        Segment(start=float(i * 10), end=float(i * 10 + 9.5), text=f"Segment number {i} content.")
        for i in range(20)  # 200 seconds of content
    ]

    rigid = chunk_segments("v1", "Test", segments, window_sec=60, overlap_sec=10, use_semantic_boundaries=False)
    semantic = chunk_segments("v1", "Test", segments, window_sec=60, overlap_sec=10, use_semantic_boundaries=True)

    # Semantic should produce roughly the same count (within ±2)
    assert abs(len(rigid) - len(semantic)) <= 2
    # Both should produce at least 3 chunks for 200s of content with 60s windows
    assert len(rigid) >= 3
    assert len(semantic) >= 3
