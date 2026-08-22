"""
src/rag/retriever.py
────────────────────
Retrieves knowledge from ChromaDB based on a query.

Returns chunks with content, metadata and relevance scores so answers can cite
sources (spec §8/§14). Degrades gracefully to empty results when the collection
has not been ingested yet.
"""
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.utils import embedding_functions

from config import get_settings
from src.observability.logger import get_logger

log = get_logger(__name__)


class KnowledgeRetriever:
    def __init__(self):
        settings = get_settings()
        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        try:
            self.collection = self.client.get_collection(
                "support_kb",
                embedding_function=self.emb_fn
            )
        except Exception:
            self.collection = None

    @property
    def available(self) -> bool:
        return self.collection is not None

    def search(
        self,
        query: str,
        n_results: int = 3,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for relevant chunks.

        Returns a list of dicts with 'content', 'metadata' and 'score'
        (cosine similarity in [0, 1]; higher is better).
        """
        if not self.collection or not query.strip():
            return []

        # Chroma's where filter requires all keys to be present in metadata.
        where = {"category": category} if category else None

        try:
            kwargs = dict(query_texts=[query], n_results=n_results)
            if where:
                kwargs["where"] = where
            results = self.collection.query(**kwargs)
        except Exception as exc:
            log.warning("kb_query_failed", error=str(exc), category=category)
            return []

        parsed_results: List[Dict[str, Any]] = []
        if results and results.get("documents") and results["documents"][0]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [None] * len(docs)
            for doc, meta, dist in zip(docs, metas, distances):
                score = max(0.0, min(1.0, 1.0 - dist)) if dist is not None else None
                parsed_results.append({
                    "content": doc,
                    "metadata": meta or {},
                    "score": round(score, 4) if score is not None else None,
                })

        log.debug(
            "kb_retrieval",
            query_length=len(query),
            category=category,
            hits=len(parsed_results),
            top_score=parsed_results[0]["score"] if parsed_results else None,
        )
        return parsed_results
