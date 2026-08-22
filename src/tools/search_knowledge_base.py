"""
src/tools/search_knowledge_base.py
──────────────────────────────────
Tool to search the approved IT knowledge base (spec §8).

Guardrails:
  • Read-only access to approved knowledge only.
  • Optional category metadata filter.
  • Low-confidence rule: when nothing relevant is found the tool says so —
    the agent must then clarify or escalate instead of guessing.
"""
import json
from typing import Optional

import agent_framework as af

from src.observability.logger import get_logger
from src.observability.tooltrace import traced_tool, record_artifact
from src.rag.retriever import KnowledgeRetriever

log = get_logger(__name__)

# Below this cosine-similarity score, results are treated as "not trusted".
LOW_CONFIDENCE_THRESHOLD = 0.30

# Lazily initialised — importing this module must NOT load the embedding model.
retriever: Optional[KnowledgeRetriever] = None


def _get_retriever() -> KnowledgeRetriever:
    global retriever
    if retriever is None:
        retriever = KnowledgeRetriever()
    return retriever


@af.tool(name="search_knowledge_base", description=(
    "Search the approved IT knowledge base for troubleshooting steps and policies. "
    "Optionally filter by category (VPN, Password, WiFi, Application, Security). "
    "Returns relevant text chunks with sources and relevance scores."
))
@traced_tool("search_knowledge_base")
def search_knowledge_base(query: str, category: Optional[str] = None) -> str:
    """
    Search the knowledge base for relevant information.

    Args:
        query: The user's query or issue description.
        category: Optional category filter, e.g. 'VPN', 'Password', 'WiFi'.
    """
    results = _get_retriever().search(query, n_results=3, category=category)

    # Drop chunks below the confidence threshold.
    trusted = [r for r in results if (r.get("score") is None or r["score"] >= LOW_CONFIDENCE_THRESHOLD)]

    if not trusted:
        return json.dumps({
            "status": "no_trusted_results",
            "message": (
                "No sufficiently relevant approved knowledge found. Do NOT guess. "
                "Ask a clarifying question, create a ticket, or escalate to a human technician."
            ),
            "query": query,
            "category": category,
        })

    formatted = []
    for res in trusted:
        meta = res["metadata"]
        entry = {
            "source": f"{meta.get('title', 'Untitled')} (Category: {meta.get('category', 'Unknown')})",
            "content": res["content"],
            "score": res.get("score"),
        }
        formatted.append(entry)
        record_artifact("sources", [{
            "title": meta.get("title", "Untitled"),
            "category": meta.get("category", "Unknown"),
            "file": meta.get("file"),
            "score": res.get("score"),
        }])

    log.info(
        "kb_tool_hit",
        category=category,
        hits=len(formatted),
        top_score=formatted[0].get("score"),
    )
    return json.dumps({
        "status": "success",
        "results": formatted,
        "instruction": "Ground your answer ONLY in these chunks and cite the source titles.",
    })
