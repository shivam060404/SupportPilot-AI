"""
src/rag/ingestor.py
───────────────────
Parses markdown files, chunks them, and stores embeddings in ChromaDB.
"""
import os
import re
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from config import get_settings, ROOT_DIR

settings = get_settings()

def parse_markdown(file_path: Path) -> dict:
    """Extracts frontmatter metadata and content from a markdown file."""
    content = file_path.read_text(encoding="utf-8")
    
    # Simple frontmatter parser
    metadata = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            content = parts[2]
            for line in frontmatter.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip()
    
    # Clean content
    content = content.strip()
    
    return {
        "metadata": metadata,
        "content": content
    }


def ingest_knowledge_base():
    """Reads all markdown files and stores them in ChromaDB."""
    kb_path = Path(ROOT_DIR) / "knowledge_base"
    
    if not kb_path.exists():
        print(f"Knowledge base path {kb_path} does not exist.")
        return

    # Initialize Chroma
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    
    # We use a simple SentenceTransformer embedding function
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model
    )
    
    # Recreate collection for simplicity
    try:
        client.delete_collection("support_kb")
    except Exception:
        pass
        
    collection = client.create_collection("support_kb", embedding_function=emb_fn)
    
    documents = []
    metadatas = []
    ids = []
    
    doc_id = 1
    for md_file in kb_path.rglob("*.md"):
        parsed = parse_markdown(md_file)
        
        # Simple chunking: paragraph level for simplicity in MVP
        # In a real app we'd use Langchain's RecursiveCharacterTextSplitter or similar
        chunks = re.split(r'\n\s*\n', parsed["content"])
        
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            
            # Enrich chunk with context
            chunk_metadata = parsed["metadata"].copy()
            chunk_metadata["file"] = md_file.name
            chunk_metadata["chunk_index"] = i
            
            documents.append(chunk.strip())
            metadatas.append(chunk_metadata)
            ids.append(f"doc_{doc_id}_chunk_{i}")
        
        doc_id += 1
        
    if documents:
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Ingested {len(documents)} chunks into ChromaDB.")
    else:
        print("No documents found to ingest.")

if __name__ == "__main__":
    ingest_knowledge_base()
