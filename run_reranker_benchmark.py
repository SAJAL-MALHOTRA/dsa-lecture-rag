import time
import subprocess
from pathlib import Path
import eval_harness as eh
from ytrag.models import Chunk
from ytrag.retriever import BM25Retriever, DenseRetriever, HybridRetriever
from ytrag.reranker import CrossEncoderReranker
from ytrag.refine import SegmentRefiner
from ytrag.dump_run import dump_run
from api.main import load_corpus

def main():
    print("=== 1. Loading corpus chunks ===")
    chunks, raw_transcripts, _ = load_corpus()
    refiner = SegmentRefiner(raw_transcripts, window=1, pad_sec=3.0)
    bm25 = BM25Retriever(chunks)
    dense_en = DenseRetriever(chunks, model_name="all-MiniLM-L6-v2")
    hybrid_en = HybridRetriever(bm25, dense_en)

    golden_path = Path("eval/golden.json")
    runs_dir = Path("runs")
    runs_dir.mkdir(exist_ok=True)
    run_rerank_file = runs_dir / "run_104_reranked.json"

    print("=== 2. Initializing Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2) ===")
    t0 = time.time()
    reranker = CrossEncoderReranker(
        base_retrieve_fn=lambda q, n: hybrid_en.retrieve(q, k=n),
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        pool_size=30,
    )
    print(f"Reranker initialized in {time.time() - t0:.2f}s")

    def retrieve_reranked(q, n):
        raw = reranker.retrieve(q, k=n)
        return refiner.refine_results(raw, q)

    print("=== 3. Dumping Cross-Encoder run for 104 queries ===")
    t_dump = time.time()
    dump_run(retrieve_reranked, golden_path, run_rerank_file, n=30)
    print(f"Run dumped to {run_rerank_file} in {time.time() - t_dump:.2f}s")

    print("\n=== 4. Dev Split Evaluation (n=39) ===")
    cmd_dev = [
        "python", "eval_harness.py",
        "--golden", str(golden_path),
        "--split", "dev",
        "--runs",
        f"hybrid_en={runs_dir / 'run_104_hybrid_en.json'}",
        f"reranked={run_rerank_file}",
        "--compare", "hybrid_en", "reranked",
        "--out", "report_rerank_104_dev.md",
    ]
    subprocess.run(cmd_dev, check=True)

    print("\n=== 5. Test Split Evaluation (n=65) ===")
    cmd_test = [
        "python", "eval_harness.py",
        "--golden", str(golden_path),
        "--split", "test",
        "--runs",
        f"hybrid_en={runs_dir / 'run_104_hybrid_en.json'}",
        f"reranked={run_rerank_file}",
        "--compare", "hybrid_en", "reranked",
        "--out", "report_rerank_104_test.md",
        "--unregistered"
    ]
    subprocess.run(cmd_test, check=True)

    print("\n=== 6. Verified Golden Set Evaluation (n=64 test) ===")
    verified_golden = Path("eval/golden.verified.json")
    if verified_golden.exists():
        cmd_verified = [
            "python", "eval_harness.py",
            "--golden", str(verified_golden),
            "--split", "test",
            "--runs",
            f"hybrid_en={runs_dir / 'run_104_hybrid_en.json'}",
            f"reranked={run_rerank_file}",
            "--compare", "hybrid_en", "reranked",
            "--out", "report_rerank_104_verified_test.md",
            "--unregistered"
        ]
        subprocess.run(cmd_verified, check=True)

    print("\nReranker benchmark completed successfully!")

if __name__ == "__main__":
    main()
