"""Unit tests for time-window chunking."""

from ytrag.models import Segment
from ytrag.chunk import chunk_segments


def test_chunk_segments_basic():
    segments = [
        Segment(start=0.0, end=10.0, text="Introduction to binary search."),
        Segment(start=10.0, end=30.0, text="First we check the middle element."),
        Segment(start=30.0, end=60.0, text="If target is smaller, we move left."),
        Segment(start=60.0, end=90.0, text="Otherwise we move right pointer."),
        Segment(start=90.0, end=120.0, text="Base case is when low exceeds high."),
    ]
    
    # 60s window with 15s overlap -> step is 45s
    chunks = chunk_segments(
        video_id="v_test",
        video_title="Binary Search Lecture",
        segments=segments,
        window_sec=60,
        overlap_sec=15,
    )
    
    assert len(chunks) > 0
    # First chunk starts at 0
    assert chunks[0].video_id == "v_test"
    assert chunks[0].start_sec == 0
    assert "Introduction to binary search." in chunks[0].text
    assert "First we check the middle element." in chunks[0].text
    
    # Check that timestamps format properly
    assert chunks[0].timestamp == "0:00"
    assert chunks[0].url == "https://www.youtube.com/watch?v=v_test&t=0s"


def test_chunk_empty_segments():
    chunks = chunk_segments("v_empty", "Empty", [])
    assert chunks == []
