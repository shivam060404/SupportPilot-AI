"""
src/rag/reranker.py
────────────────────
Cross-encoder reranking of RAG retrieval results.

After ANN retrieval from ChromaDB, reranking with a cross-encoder
significantly improves precision by jointly scoring (query, document) pairs.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, lightweight, well-tested)

Degrades gracefully if sentence-transformers is not installed or model fails.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from src.observability.logger import get_logger

log = get_logger(__name__)

RERANKER_MODEL = os.getenv(
    "RERANKER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"


class CrossEncoderReranker:
    """Reranks retrieval results using a cross-encoder model."""

    def __init__(self, model_name: str = RERANKER_MODEL) -> None:
        self.model_name = model_name
        self._model = None
        self._available = False

    def _load(self) -> bool:
        if self._model is not None:
            return self._available
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            self._available = True
            log.info("reranker_loaded", model=self.model_name)
        except Exception as exc:
            log.warning("reranker_load_failed", model=self.model_name, error=str(exc))
            self._available = False
        return self._available

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Rerank retrieval results by relevance to query.

        Args:
            query: The user's query.
            results: List of dicts with 'content', 'metadata', 'score'.
            top_k: Number of top results to return after reranking.

        Returns:
            Top-k results sorted by cross-encoder score (descending).
        """
        if not RERANKER_ENABLED or not results:
            return results[:top_k]

        if not self._load():
            # Fallback: return original ANN results
            return results[:top_k]

        pairs = [(query, r.get("content", "")) for r in results]

        try:
            scores = self._model.predict(pairs)
            for result, score in zip(results, scores):
                result["rerank_score"] = float(score)
            reranked = sorted(results, key=lambda r: r.get("rerank_score", 0), reverse=True)
            log.debug(
                "reranker_applied",
                input_count=len(results),
                output_count=min(top_k, len(reranked)),
                top_score=reranked[0]["rerank_score"] if reranked else None,
            )
            return reranked[:top_k]
        except Exception as exc:
            log.warning("reranker_predict_failed", error=str(exc))
            return results[:top_k]


# Module-level singleton
_reranker: Optional[CrossEncoderReranker] = None


def get_reranker() -> CrossEncoderReranker:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker
