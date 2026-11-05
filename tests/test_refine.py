"""Tests for ytrag.refine."""

from ytrag.models import Chunk, RetrievalResult
from ytrag.refine import SegmentRefiner


def test_segment_refiner():
    transcripts = {
        "v1": [
            (0.0, 10.0, "welcome back to the lecture"),
            (10.0, 50.0, "today we discuss various things"),
            (50.0, 75.0, "here is the tortoise and hare algorithm"),
            (75.0, 100.0, "fast pointer moves by two"),
        ]
    }
    refiner = SegmentRefiner(transcripts, window=1, pad_sec=3.0)

    chunk = Chunk(
        chunk_id="v1:0",
        video_id="v1",
        video_title="Title",
        start_sec=0,
        end_sec=80,
        text="welcome back today we discuss here is the tortoise and hare algorithm",
    )

    refined = refiner.refine_chunk(chunk, "tortoise and hare")
    # Best segment starts at 50.0. With 3s pad -> 47.0
    assert refined.start_sec == 47
    assert refined.end_sec == 80
