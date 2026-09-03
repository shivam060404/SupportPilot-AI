"""
src/rag/embedder.py
────────────────────
Embedding model wrapper with caching.

Provides a consistent interface over SentenceTransformer. Caches
repeated embeddings (LRU) to avoid redundant model calls for common queries.
"""
from __future__ import annotations

import functools
from typing import List, Optional

from config import get_settings


class Embedder:
    """
    Wraps SentenceTransformer for document and query embedding.

    Attributes:
        model_name: Name of the SentenceTransformer model.
        cache_size: Number of query embeddings to cache (LRU).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache_size: int = 256,
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self._cache_size = cache_size

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of documents (for indexing)."""
        model = self._get_model()
        embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query (with LRU caching)."""
        return self._cached_embed(text)

    @functools.lru_cache(maxsize=256)
    def _cached_embed(self, text: str) -> List[float]:
        model = self._get_model()
        return model.encode([text], show_progress_bar=False)[0].tolist()

    @property
    def dimension(self) -> int:
        """Return the embedding dimension of the model."""
        model = self._get_model()
        return model.get_sentence_embedding_dimension()
