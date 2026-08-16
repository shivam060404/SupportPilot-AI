"""
src/rag/retriever.py
────────────────────
Retrieves knowledge from ChromaDB based on a query.
"""
from typing import List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions
from config import get_settings

settings = get_settings()

class KnowledgeRetriever:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        try:
            self.collection = self.client.get_collection(
                "support_kb", 
                embedding_function=self.emb_fn
            )
        except ValueError:
            self.collection = None
            
    def search(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for relevant chunks.
        Returns a list of dicts with 'content' and 'metadata'.
        """
        if not self.collection:
            return []
            
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        parsed_results = []
        if results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            for doc, meta in zip(docs, metas):
                parsed_results.append({
                    "content": doc,
                    "metadata": meta
                })
                
        return parsed_results
