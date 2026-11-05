"""Unit tests for CrossEncoderReranker."""

from ytrag.models import Chunk, RetrievalResult
from ytrag.reranker import CrossEncoderReranker


def make_dummy_chunk(cid: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=cid,
        video_id="v1",
        video_title="Title",
        start_sec=10,
        end_sec=80,
        text=text,
    )


def test_reranker_basic():
    chunks = [
        make_dummy_chunk("c1", "completely irrelevant text about cooking pasta"),
        make_dummy_chunk("c2", "binary search checks low and high pointers"),
    ]
    
    def mock_retrieve(q: str, n: int) -> list[RetrievalResult]:
        # base retriever puts irrelevant first
        return [
            RetrievalResult(chunks[0], 10.0, "base"),
            RetrievalResult(chunks[1], 5.0, "base"),
        ]

    reranker = CrossEncoderReranker(mock_retrieve, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", pool_size=2)
    results = reranker.retrieve("binary search algorithm", k=2)

    assert len(results) == 2
    # The cross-encoder should easily rank the relevant text first
    assert results[0].chunk.chunk_id == "c2"
    assert results[1].chunk.chunk_id == "c1"
    assert results[0].score > results[1].score
