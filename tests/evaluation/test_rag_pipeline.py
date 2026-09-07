"""
tests/test_rag_pipeline.py
──────────────────────────
Unit tests for the RAG chunker and retriever components.
"""
from src.rag.chunker import SemanticChunker

def test_semantic_chunker():
    chunker = SemanticChunker(chunk_size=50, chunk_overlap=10)
    
    text = "This is a test of the semantic chunker. It should split this text into multiple chunks based on the size limit."
    chunks = chunker.chunk(text)
    
    assert len(chunks) > 1
    # Check that each chunk is roughly within the size limit (some might be slightly larger depending on separators)
    assert all(len(c.content) <= 60 for c in chunks)
    
    # Check overlap (the second chunk should contain text from the end of the first chunk)
    overlap = chunks[1].content.split()[0]
    assert overlap in chunks[0].content
