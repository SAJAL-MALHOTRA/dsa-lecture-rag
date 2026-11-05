"""
Retriever for pattern code templates and conceptual explanations
from awesome-leetcode-resources.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple
from rank_bm25 import BM25Okapi

from data_ingestion.schemas import PatternChunk

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PATTERNS_CORPUS_PATH = BASE_DIR / "data" / "patterns_corpus.json"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


class PatternRetriever:
    """
    Retrieves algorithmic pattern code templates and prose explanations.
    """

    def __init__(self, corpus_path: Path | str = PATTERNS_CORPUS_PATH):
        self.corpus_path = Path(corpus_path)
        self.chunks: List[PatternChunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self._load()

    def _load(self):
        if not self.corpus_path.exists():
            logger.warning("Patterns corpus not found at %s", self.corpus_path)
            return

        try:
            raw_data = json.loads(self.corpus_path.read_text(encoding="utf-8"))
            self.chunks = [PatternChunk(**item) for item in raw_data]
            tokenized_corpus = [
                _tokenize(f"{c.pattern_name} {c.title} {c.canonical_topic} {c.text}")
                for c in self.chunks
            ]
            self.bm25 = BM25Okapi(tokenized_corpus)
            logger.info("Loaded %d pattern chunks into PatternRetriever", len(self.chunks))
        except Exception as exc:
            logger.error("Error loading pattern corpus: %s", exc)

    def retrieve(
        self,
        query: str,
        k: int = 3,
        canonical_topic: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Tuple[PatternChunk, float]]:
        """
        Retrieves top matching pattern chunks with optional topic or language filters.
        """
        if not self.bm25 or not self.chunks:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        # Detect language preference from query if not specified
        q_lower = query.lower()
        if not language:
            if "c++" in q_lower or "cpp" in q_lower:
                language = "cpp"
            elif "python" in q_lower or "py" in q_lower:
                language = "python"
            elif "java" in q_lower:
                language = "java"

        scores = self.bm25.get_scores(tokens)
        scored: List[Tuple[PatternChunk, float]] = []

        for chunk, score in zip(self.chunks, scores):
            final_score = float(score)

            # Boost if canonical topic matches
            if canonical_topic and chunk.canonical_topic == canonical_topic:
                final_score += 10.0

            # Language filtering / boosting
            if language and chunk.language not in ("general", language):
                final_score -= 15.0
            elif language and chunk.language == language:
                final_score += 8.0

            if final_score > 0.0:
                scored.append((chunk, final_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]


_global_pattern_retriever: Optional[PatternRetriever] = None


def get_pattern_retriever() -> PatternRetriever:
    global _global_pattern_retriever
    if _global_pattern_retriever is None:
        _global_pattern_retriever = PatternRetriever()
    return _global_pattern_retriever


if __name__ == "__main__":
    retriever = PatternRetriever()
    results = retriever.retrieve("Explain the sliding window pattern in C++", k=2)
    for chunk, score in results:
        print(f"[{score:.2f}] ({chunk.content_type} / {chunk.language}) {chunk.title}")
