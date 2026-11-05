"""
Unit tests for repetition filtering and title context chunking.
"""

from ytrag.models import Segment
from ytrag.chunk import chunk_segments, is_repetitive


def test_is_repetitive():
    hallucination_text = "Thank you for watching. Thank you for watching. Thank you for watching. Thank you for watching."
    assert is_repetitive(hallucination_text, threshold=0.6) is True

    normal_text = "First we find the middle element. Then we compare target with arr[mid]. If smaller, move left."
    assert is_repetitive(normal_text, threshold=0.6) is False


def test_chunking_drops_repetitive_loop():
    segments = [
        Segment(start=0.0, end=15.0, text="Thank you for watching. Thank you for watching. Thank you for watching. Thank you for watching."),
        Segment(start=15.0, end=35.0, text="Now let us discuss the two pointer approach for reversing."),
        Segment(start=35.0, end=60.0, text="We initialize left at 0 and right at n - 1."),
    ]

    chunks = chunk_segments("vid_test", "Two Pointers Lecture", segments, window_sec=40, overlap_sec=10)
    # The first chunk solely containing the repetitive loop should be dropped
    for c in chunks:
        assert not (c.start_sec == 0 and "Thank you for watching" in c.text and "two pointer" not in c.text)


def test_chunking_prefixes_title():
    segments = [
        Segment(start=0.0, end=20.0, text="Let us review the base case of recursion."),
    ]
    chunks = chunk_segments("v_rec", "Recursion Tree Lecture", segments, prefix_title=True)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Recursion Tree Lecture\n\n")
