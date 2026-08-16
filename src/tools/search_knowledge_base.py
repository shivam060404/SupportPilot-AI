"""
src/tools/search_knowledge_base.py
──────────────────────────────────
Tool to search the knowledge base.
"""
from typing import Dict, Any, List
import agent_framework as af
from src.rag.retriever import KnowledgeRetriever
import json

# Initialize retriever once
retriever = KnowledgeRetriever()

@af.tool(name="search_knowledge_base", description="Search the approved IT knowledge base for troubleshooting steps and policies. Returns relevant text chunks and their sources.")
def search_knowledge_base(query: str) -> str:
    """
    Search the knowledge base for relevant information.
    
    Args:
        query: The user's query or issue description.
        
    Returns:
        JSON string of retrieved chunks with metadata.
    """
    results = retriever.search(query)
    if not results:
        return json.dumps({"status": "no_results_found", "message": "No relevant knowledge base articles found."})
    
    formatted_results = []
    for res in results:
        meta = res["metadata"]
        formatted_results.append({
            "source": f"{meta.get('title', 'Unknown Title')} (Category: {meta.get('category', 'Unknown')})",
            "content": res["content"]
        })
        
    return json.dumps({"status": "success", "results": formatted_results})
