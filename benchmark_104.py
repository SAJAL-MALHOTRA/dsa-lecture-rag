import subprocess
from pathlib import Path
import eval_harness as eh
from ytrag.models import Chunk
from ytrag.retriever import BM25Retriever, DenseRetriever, HybridRetriever
from ytrag.refine import SegmentRefiner
from ytrag.dump_run import dump_run
from api.main import load_corpus

def main():
    print("=== 1. Loading corpus chunks ===")
    chunks, raw_transcripts, _ = load_corpus()
    refiner = SegmentRefiner(raw_transcripts, window=1, pad_sec=3.0)
    bm25 = BM25Retriever(chunks)

    golden_path = Path("eval/golden.json")
    runs_dir = Path("runs")
    runs_dir.mkdir(exist_ok=True)

    # 1. BM25 run
    run_bm25_file = runs_dir / "run_104_bm25.json"
    if not run_bm25_file.exists():
        print("=== 2. Dumping BM25 run for 104 queries ===")
        def retrieve_bm25(q, n):
            raw = bm25.retrieve(q, k=n)
            return refiner.refine_results(raw, q)
        dump_run(retrieve_bm25, golden_path, run_bm25_file, n=30)
    else:
        print(f"=== 2. Reusing cached {run_bm25_file.name} ===")

    # 2. English Hybrid run
    run_en_file = runs_dir / "run_104_hybrid_en.json"
    if not run_en_file.exists():
        print("=== 3. Dumping Hybrid English run for 104 queries ===")
        dense_en = DenseRetriever(chunks, model_name="all-MiniLM-L6-v2")
        hybrid_en = HybridRetriever(bm25, dense_en)
        def retrieve_en(q, n):
            raw = hybrid_en.retrieve(q, k=n)
            return refiner.refine_results(raw, q)
        dump_run(retrieve_en, golden_path, run_en_file, n=30)
    else:
        print(f"=== 3. Reusing cached {run_en_file.name} ===")

    # 3. Multilingual Hybrid run
    run_multi_file = runs_dir / "run_104_hybrid_multi.json"
    if not run_multi_file.exists():
        print("=== 4. Dumping Hybrid Multilingual run for 104 queries ===")
        dense_multi = DenseRetriever(chunks, model_name="paraphrase-multilingual-MiniLM-L12-v2")
        hybrid_multi = HybridRetriever(bm25, dense_multi)
        def retrieve_multi(q, n):
            raw = hybrid_multi.retrieve(q, k=n)
            return refiner.refine_results(raw, q)
        dump_run(retrieve_multi, golden_path, run_multi_file, n=30)
    else:
        print(f"=== 4. Reusing cached {run_multi_file.name} ===")

    print("=== 5. Running Eval Harness with TOST on dev split (n=39) ===")
    cmd_dev = [
        "python", "eval_harness.py",
        "--golden", str(golden_path),
        "--split", "dev",
        "--runs",
        f"bm25={run_bm25_file}",
        f"hybrid_en={run_en_file}",
        f"hybrid_multi={run_multi_file}",
        "--compare", "hybrid_en", "hybrid_multi",
        "--transcripts", "transcripts/",
        "--out", "report_104_dev.md",
        "--json-out", "report_104_dev.json",
    ]
    subprocess.run(cmd_dev, check=True)

    print("=== 6. Running Eval Harness with TOST on test split (n=65) ===")
    cmd_test = [
        "python", "eval_harness.py",
        "--golden", str(golden_path),
        "--split", "test",
        "--runs",
        f"bm25={run_bm25_file}",
        f"hybrid_en={run_en_file}",
        f"hybrid_multi={run_multi_file}",
        "--compare", "hybrid_en", "hybrid_multi",
        "--transcripts", "transcripts/",
        "--out", "report_104_test.md",
        "--json-out", "report_104_test.json",
        "--unregistered"
    ]
    subprocess.run(cmd_test, check=True)
    print("\nALL 104-QUERY BENCHMARKS WITH TOST EQUIVALENCE COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
