"""
CLI runner for multi-source DSA resource ingestion.
Fetches / updates the three external repositories:
1. ashishps1/awesome-leetcode-resources (Patterns & Code Corpus)
2. avinash201199/DSA-KIT (Visualizers & Tools Catalog)
3. helloworldbyprince/Complete-DSA-Preparation (Curriculum Graph & Problems)

Generates topic_resources.json, curriculum_graph.json, and patterns_corpus.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from data_ingestion.fetcher import ensure_external_repos
from data_ingestion.parse_patterns import build_and_save_patterns_corpus
from data_ingestion.parse_dsa_kit import build_and_save_topic_resources
from data_ingestion.parse_curriculum import build_and_save_curriculum_graph
from ytrag.pattern_retriever import PatternRetriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_external_dsa")


def run_ingestion(
    force_update: bool = False,
    data_dir: Path | str = BASE_DIR / "data",
) -> dict:
    """
    Executes the complete multi-source ingestion pipeline.
    """
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    logger.info("=== STEP 1: Ensuring External Repositories ===")
    repo_paths = ensure_external_repos(
        target_dir=data_path / "external_sources",
        force_update=force_update,
    )

    logger.info("=== STEP 2: Ingesting DSA-KIT Visualizers & Tools ===")
    topic_resources_out = data_path / "topic_resources.json"
    topic_resources = build_and_save_topic_resources(
        readme_path=repo_paths["DSA-KIT"] / "README.md",
        output_path=topic_resources_out,
    )

    logger.info("=== STEP 3: Ingesting Complete-DSA-Preparation Curriculum Graph ===")
    curriculum_graph_out = data_path / "curriculum_graph.json"
    curriculum_graph = build_and_save_curriculum_graph(
        readme_path=repo_paths["Complete-DSA-Preparation"] / "README.md",
        output_path=curriculum_graph_out,
    )

    logger.info("=== STEP 4: Ingesting Awesome-LeetCode-Resources Pattern Corpus ===")
    patterns_corpus_out = data_path / "patterns_corpus.json"
    pattern_chunks = build_and_save_patterns_corpus(
        repo_dir=repo_paths["awesome-leetcode-resources"],
        output_path=patterns_corpus_out,
    )

    logger.info("=== STEP 5: Indexing Pattern Chunks in PatternRetriever ===")
    pattern_retriever = PatternRetriever(corpus_path=patterns_corpus_out)

    elapsed = round(time.perf_counter() - t0, 2)
    summary = {
        "status": "success",
        "elapsed_sec": elapsed,
        "topic_resources_count": len(topic_resources),
        "curriculum_topics_count": len(curriculum_graph),
        "pattern_chunks_count": len(pattern_chunks),
        "files_generated": [
            str(topic_resources_out),
            str(curriculum_graph_out),
            str(patterns_corpus_out),
        ],
    }

    logger.info("Multi-source DSA ingestion completed in %.2fs!", elapsed)
    logger.info("Summary: %s", json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Multi-source DSA ingestion CLI")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Force git pull / update for cached external repositories",
    )
    parser.add_argument(
        "--data-dir",
        default=str(BASE_DIR / "data"),
        help="Target data directory for generated JSON files",
    )
    args = parser.parse_args()
    summary = run_ingestion(force_update=args.update, data_dir=args.data_dir)
    print("\nIngestion Completed Successfully:")
    print(f"- Topic Resources: {summary['topic_resources_count']}")
    print(f"- Curriculum Topics: {summary['curriculum_topics_count']}")
    print(f"- Pattern Chunks: {summary['pattern_chunks_count']}")
    print(f"- Total Time: {summary['elapsed_sec']}s")


if __name__ == "__main__":
    main()
