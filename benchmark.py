"""
Run the evaluation benchmark on the golden test set and produce the ablation table.
Compares BM25, Dense semantic, and Hybrid (RRF) retrieval.
"""

import json
from pathlib import Path

from ytrag.models import Segment, Chunk
from ytrag.chunk import chunk_segments
from ytrag.retriever import BM25Retriever, DenseRetriever, HybridRetriever
from ytrag.evaluate import load_golden_set, evaluate, ablation_table


def load_all_chunks(
    transcript_dir: Path,
    window_sec: int = 75,
    overlap_sec: int = 15,
) -> list[Chunk]:
    """Load transcript files and segment them into temporal Chunks."""
    chunks: list[Chunk] = []
    files = list(transcript_dir.glob("*.json"))
    
    for p in files:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        vid_id = data["video_id"]
        title = data["title"]
        raw_segs = data["segments"]
        
        segments = [
            Segment(
                start=float(s["start"]),
                end=float(s["start"] + s.get("duration", 0.0)),
                text=s["text"],
            )
            for s in raw_segs
        ]
        
        vid_chunks = chunk_segments(
            video_id=vid_id,
            video_title=title,
            segments=segments,
            window_sec=window_sec,
            overlap_sec=overlap_sec,
        )
        chunks.extend(vid_chunks)

    return chunks


def main():
    transcript_dir = Path("transcripts")
    golden_path = Path("eval/golden.json")
    
    if not golden_path.exists():
        print(f"Error: {golden_path} does not exist.")
        return

    print("=== 1. Loading and Chunking Transcripts ===")
    chunks = load_all_chunks(transcript_dir, window_sec=75, overlap_sec=15)
    print(f"Total video files: {len(list(transcript_dir.glob('*.json')))}")
    print(f"Total indexed chunks: {len(chunks)}")
    print()

    print("=== 2. Loading Golden Test Queries ===")
    queries = load_golden_set(golden_path)
    print(f"Loaded {len(queries)} evaluation queries.")
    print()

    # 1. BM25
    print("=== 3. Evaluating BM25 Lexical Retriever ===")
    bm25 = BM25Retriever(chunks)
    report_bm25_k3 = evaluate(queries, bm25.retrieve, retriever_name="BM25", k=3)
    report_bm25_k5 = evaluate(queries, bm25.retrieve, retriever_name="BM25", k=5)

    # 2. Dense Semantic
    print("=== 4. Evaluating Dense Semantic Retriever (MiniLM) ===")
    dense = DenseRetriever(chunks, model_name="all-MiniLM-L6-v2")
    report_dense_k3 = evaluate(queries, dense.retrieve, retriever_name="Dense (MiniLM)", k=3)
    report_dense_k5 = evaluate(queries, dense.retrieve, retriever_name="Dense (MiniLM)", k=5)

    # 3. Hybrid RRF
    print("=== 5. Evaluating Hybrid Retriever (BM25 + Dense RRF) ===")
    hybrid = HybridRetriever(bm25, dense)
    report_hybrid_k3 = evaluate(queries, hybrid.retrieve, retriever_name="Hybrid (RRF)", k=3)
    report_hybrid_k5 = evaluate(queries, hybrid.retrieve, retriever_name="Hybrid (RRF)", k=5)

    print("\n" + "="*65)
    print("EMPIRICAL ABLATION RESULTS (Measured on Golden Set)")
    print("="*65)
    print(ablation_table([
        report_bm25_k3,
        report_dense_k3,
        report_hybrid_k3,
        report_bm25_k5,
        report_dense_k5,
        report_hybrid_k5,
    ]))
    print()

    print("=== Inspecting Question 02 (The BM25 failure case) across all 3 ===")
    q02 = next(q for q in queries if q.query_id == "q02")
    
    print("\n--- BM25 (Top 3) ---")
    for r in bm25.retrieve(q02.query, k=3):
        print(f"  [{r.chunk.timestamp} - {r.chunk.end_sec}s] {r.chunk.video_title} (score: {r.score:.3f})")
        
    print("\n--- Dense (Top 3) ---")
    for r in dense.retrieve(q02.query, k=3):
        print(f"  [{r.chunk.timestamp} - {r.chunk.end_sec}s] {r.chunk.video_title} (score: {r.score:.3f})")

    print("\n--- Hybrid RRF (Top 3) ---")
    for r in hybrid.retrieve(q02.query, k=3):
        print(f"  [{r.chunk.timestamp} - {r.chunk.end_sec}s] {r.chunk.video_title} (score: {r.score:.5f})")


if __name__ == "__main__":
    main()
