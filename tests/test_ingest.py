"""
Unit tests for the resilient ingestion pipeline.
"""

from ytrag.ingest import compute_sha256, fetch_via_ytdlp, load_manifest


def test_compute_sha256():
    h1 = compute_sha256("test data")
    h2 = compute_sha256("test data")
    h3 = compute_sha256("different data")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def test_load_manifest_structure():
    m = load_manifest()
    assert isinstance(m, dict)
    assert "videos" in m


def test_fetch_via_ytdlp_nonexistent():
    # Calling with nonexistent video ID returns error gracefully without throwing uncaught exception
    segs, err = fetch_via_ytdlp("nonexistent_video_xyz987")
    assert segs is None
    assert err != ""


def test_ingest_phonetic_normalization():
    from ytrag.phonetic_normalizer import normalize_dsa_text
    raw_segments = [
        {"start": 1.0, "end": 5.0, "text": "let us apply can dance algorithm for this sab array"},
        {"start": 5.5, "end": 10.0, "text": "we do a dry wine and inspect numbers of eye"},
    ]
    for seg in raw_segments:
        seg["text"] = normalize_dsa_text(seg["text"])

    assert "kadane algorithm" in raw_segments[0]["text"]
    assert "subarray" in raw_segments[0]["text"]
    assert "dry run" in raw_segments[1]["text"]
    assert "nums[i]" in raw_segments[1]["text"]
