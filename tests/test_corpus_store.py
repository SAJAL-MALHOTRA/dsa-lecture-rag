"""
Unit tests for the SQLite immutable corpus storage layer.
"""

import tempfile
from pathlib import Path
from ytrag.models import Segment
from ytrag.corpus_store import (
    init_db,
    insert_video_transcript,
    rebuild_chunks,
    load_chunks_from_db,
    load_raw_transcripts_from_db,
    get_corpus_stats,
    sync_transcripts_directory_to_db,
)


def test_init_db_and_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_corpus.sqlite"
        init_db(db_path)
        stats = get_corpus_stats(db_path)
        assert stats["total_videos"] == 0
        assert stats["total_segments"] == 0
        assert stats["total_chunks"] == 0
        assert stats["schema_version"] == "1.0.0"


def test_insert_video_and_rebuild_chunks():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_corpus.sqlite"
        init_db(db_path)

        segments = [
            {"start": 0.0, "end": 25.0, "text": "let us discuss can dance algorithm for this sab array"},
            {"start": 26.0, "end": 60.0, "text": "we maintain cur_sum and numbers of eye"},
            {"start": 62.0, "end": 90.0, "text": "now let's code this optimal approach step by step"},
        ]

        insert_video_transcript(
            db_path=db_path,
            video_id="v_kadane",
            title="Kadane Algorithm Lecture",
            duration_sec=90,
            segments=segments,
            normalize_phonetics=True,
        )

        stats = get_corpus_stats(db_path)
        assert stats["total_videos"] == 1
        assert stats["total_segments"] == 3

        # Verify phonetic normalization occurred
        raw_transcripts, videos_meta = load_raw_transcripts_from_db(db_path)
        assert "v_kadane" in raw_transcripts
        assert "kadane algorithm" in raw_transcripts["v_kadane"][0][2]
        assert "subarray" in raw_transcripts["v_kadane"][0][2]
        assert "nums[i]" in raw_transcripts["v_kadane"][1][2]

        # Rebuild chunks
        chunk_count = rebuild_chunks(db_path, window_sec=60, overlap_sec=15)
        assert chunk_count > 0

        chunks = load_chunks_from_db(db_path)
        assert len(chunks) == chunk_count
        assert chunks[0].video_id == "v_kadane"
        assert chunks[0].start_sec >= 0


def test_sync_transcripts_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sync.sqlite"
        res = sync_transcripts_directory_to_db("transcripts", db_path)
        assert res["videos_imported"] >= 8
        assert res["total_chunks"] > 0
        stats = get_corpus_stats(db_path)
        assert stats["total_videos"] >= 8
