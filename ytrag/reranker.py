"""
Cross-Encoder reranker module.

Takes candidate chunks retrieved by an initial retriever (BM25, Dense, or Hybrid)
and re-scores them using a full attention cross-encoder model.
"""

from __future__ import annotations

from typing import Callable
from sentence_transformers import CrossEncoder

from .models import Chunk, RetrievalResult


class CrossEncoderReranker:
    """
    Re-ranks candidates from a base retriever using a CrossEncoder.
    """

    def __init__(
        self,
        base_retrieve_fn: Callable[[str, int], list[RetrievalResult]],
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        pool_size: int = 30,
        device: str | None = None,
    ):
        import torch
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.base_retrieve = base_retrieve_fn
        self.model = CrossEncoder(model_name, device=device)
        self.pool_size = pool_size
        self.model_name = model_name

    def retrieve(self, query: str, k: int = 3) -> list[RetrievalResult]:
        # Fetch initial candidate pool (ensuring pool is at least k)
        fetch_n = max(self.pool_size, k)
        candidates = self.base_retrieve(query, fetch_n)
        if not candidates:
            return []

        # Prepare (query, passage) pairs
        pairs = [(query, r.chunk.text) for r in candidates]
        scores = self.model.predict(pairs, show_progress_bar=False, batch_size=32)

        # Pair candidates with cross-encoder scores and sort descending
        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for orig_res, score in scored[:k]:
            results.append(
                RetrievalResult(
                    chunk=orig_res.chunk,
                    score=float(score),
                    retriever_name=f"reranked_{self.model_name.split('/')[-1]}",
                )
            )
        return results
