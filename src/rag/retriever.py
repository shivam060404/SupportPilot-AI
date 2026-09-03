"""
src/rag/retriever.py
────────────────────
Enhanced RAG retriever: ChromaDB ANN → cross-encoder reranking → source citation.

Pipeline:
  1. Embed query with SentenceTransformer
  2. ANN retrieval from ChromaDB (top-n_candidates)
  3. Cross-encoder reranking → top-k results
  4. Confidence threshold filtering
  5. Return structured results with citation metadata

Degrades gracefully to empty results when ChromaDB collection is not ready.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions

from config import get_settings
from src.observability.logger import get_logger
from src.rag.reranker import get_reranker

log = get_logger(__name__)

# Initial ANN candidates before reranking (more candidates = better reranker results)
ANN_CANDIDATES = 10
# Minimum confidence threshold for results returned to the agent
CONFIDENCE_THRESHOLD = 0.10


class KnowledgeRetriever:
    """
    Enhanced retriever with ANN + cross-encoder reranking pipeline.

    Attributes:
        n_results: Final number of results to return after reranking.
        n_candidates: Initial ANN candidates to fetch for reranking.
        threshold: Minimum relevance score to include a result.
    """

    def __init__(
        self,
        n_results: int = 3,
        n_candidates: int = ANN_CANDIDATES,
        threshold: float = CONFIDENCE_THRESHOLD,
    ) -> None:
        settings = get_settings()
        self.n_results = n_results
        self.n_candidates = n_candidates
        self.threshold = threshold

        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        self._reranker = get_reranker()

        try:
            self._collection = self._client.get_collection(
                "support_kb",
                embedding_function=self._emb_fn,
            )
            log.info(
                "retriever_initialized",
                collection="support_kb",
                count=self._collection.count(),
            )
        except Exception as exc:
            log.warning("retriever_collection_missing", error=str(exc))
            self._collection = None

    def reload_collection(self) -> None:
        """Reload the ChromaDB collection (call after re-ingestion)."""
        try:
            settings = get_settings()
            self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            self._collection = self._client.get_collection(
                "support_kb",
                embedding_function=self._emb_fn,
            )
            log.info("retriever_collection_reloaded", count=self._collection.count())
        except Exception as exc:
            log.warning("retriever_reload_failed", error=str(exc))
            self._collection = None

    @property
    def available(self) -> bool:
        return self._collection is not None

    def search(
        self,
        query: str,
        n_results: Optional[int] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge base using ANN + reranking pipeline.

        Args:
            query: User's query string.
            n_results: Number of results to return (default: self.n_results).
            category: Optional category filter (VPN, Password, WiFi, etc.).

        Returns:
            List of dicts: {content, metadata, score, rerank_score, citation}
        """
        if not self._collection or not query.strip():
            return []

        k = n_results or self.n_results
        n_fetch = min(self.n_candidates, self._collection.count() or 1)
        where = {"category": category} if category else None

        try:
            kwargs: Dict[str, Any] = dict(
                query_texts=[query],
                n_results=n_fetch,
            )
            if where:
                kwargs["where"] = where
            raw = self._collection.query(**kwargs)
        except Exception as exc:
            log.warning("retriever_query_failed", error=str(exc), category=category)
            return []

        # Parse ChromaDB response
        candidates: List[Dict[str, Any]] = []
        if raw and raw.get("documents") and raw["documents"][0]:
            docs = raw["documents"][0]
            metas = raw.get("metadatas", [[]])[0] or [{}] * len(docs)
            distances = raw.get("distances", [[]])[0] or [None] * len(docs)

            for doc, meta, dist in zip(docs, metas, distances):
                score = max(0.0, min(1.0, 1.0 - dist)) if dist is not None else 0.5
                candidates.append({
                    "content": doc,
                    "metadata": meta or {},
                    "score": round(score, 4),
                })

        # Rerank candidates
        reranked = self._reranker.rerank(query, candidates, top_k=k)

        # Filter by confidence threshold and build citation metadata
        results = []
        for item in reranked:
            ann_score = item.get("score", 0)
            rerank_score = item.get("rerank_score")

            # Use rerank_score if available (more reliable), else ann_score
            effective_score = rerank_score if rerank_score is not None else ann_score

            if effective_score < self.threshold and ann_score < self.threshold:
                continue

            meta = item.get("metadata", {})
            item["citation"] = {
                "title": meta.get("title", meta.get("file", "Knowledge Base")),
                "category": meta.get("category"),
                "file": meta.get("file"),
                "section": meta.get("section_title"),
            }
            results.append(item)

        log.debug(
            "retriever_search",
            query_length=len(query),
            category=category,
            candidates=len(candidates),
            results=len(results),
            top_score=results[0].get("score") if results else None,
        )

        # Record metrics
        try:
            from src.observability.metrics import record_rag_score
            for r in results:
                if r.get("score") is not None:
                    record_rag_score(r["score"])
        except Exception:
            pass

        return results
