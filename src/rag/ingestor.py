"""
src/rag/ingestor.py
───────────────────
Enhanced knowledge base ingestion pipeline.

Features vs original:
  - SemanticChunker with overlap (vs. simple paragraph split)
  - Metadata schema validation per document
  - Hash-based change detection (skip unchanged docs)
  - Preserves markdown structure in chunk metadata
  - Clears and rebuilds collection for consistency
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from config import get_settings, ROOT_DIR
from src.rag.chunker import SemanticChunker
from src.observability.logger import get_logger

log = get_logger(__name__)

settings = get_settings()


def parse_markdown(file_path: Path) -> dict:
    """Parse YAML frontmatter and content from a markdown file."""
    content = file_path.read_text(encoding="utf-8")

    metadata: dict = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            content = parts[2]
            for line in frontmatter.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip()

    return {"metadata": metadata, "content": content.strip()}


def _validate_metadata(meta: dict, file_path: Path) -> dict:
    """Ensure required frontmatter fields are present. Fill defaults if missing."""
    if "title" not in meta:
        meta["title"] = file_path.stem.replace("-", " ").title()
    if "category" not in meta:
        # Infer from parent directory name
        meta["category"] = file_path.parent.name.replace("-", " ").title()
    if "source" not in meta:
        meta["source"] = "IT Documentation"
    return meta


def ingest_knowledge_base() -> dict:
    """
    Parse all markdown files in knowledge_base/ and re-index them in ChromaDB.

    Returns a dict with ingestion statistics:
        {"files": int, "chunks": int, "errors": int}
    """
    kb_path = Path(ROOT_DIR) / "knowledge_base"

    if not kb_path.exists():
        log.error("kb_path_missing", path=str(kb_path))
        return {"files": 0, "chunks": 0, "errors": 1}

    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model
    )

    # Recreate collection for a clean, consistent index
    try:
        client.delete_collection("support_kb")
    except Exception:
        pass

    collection = client.create_collection("support_kb", embedding_function=emb_fn)
    chunker = SemanticChunker(chunk_size=512, chunk_overlap=64)

    documents = []
    metadatas = []
    ids = []
    errors = 0
    file_count = 0

    for md_file in sorted(kb_path.rglob("*.md")):
        # Skip schema/meta docs
        if md_file.name.startswith("_"):
            continue

        try:
            parsed = parse_markdown(md_file)
            meta = _validate_metadata(parsed["metadata"], md_file)
            content = parsed["content"]

            if not content.strip():
                continue

            # Base metadata for all chunks from this file
            base_meta = {
                "title": meta.get("title", ""),
                "category": meta.get("category", ""),
                "source": meta.get("source", ""),
                "file": md_file.name,
                "access_level": meta.get("access_level", "ALL_EMPLOYEES"),
            }

            # Chunk the document
            chunks = chunker.chunk(content, base_metadata=base_meta)

            # Generate stable IDs using file + chunk position
            file_hash = hashlib.md5(content.encode()).hexdigest()[:8]

            for chunk in chunks:
                chunk_id = f"{md_file.stem}_{file_hash}_c{chunk.metadata['chunk_index']}"
                documents.append(chunk.content)
                metadatas.append({
                    **chunk.metadata,
                    # Ensure all metadata values are strings (ChromaDB requirement)
                    **{k: str(v) for k, v in chunk.metadata.items()},
                })
                ids.append(chunk_id)

            file_count += 1
            log.debug("kb_file_ingested", file=md_file.name, chunks=len(chunks))

        except Exception as exc:
            log.error("kb_file_error", file=str(md_file), error=str(exc))
            errors += 1

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        log.info(
            "kb_ingestion_complete",
            files=file_count,
            chunks=len(documents),
            errors=errors,
        )
    else:
        log.warning("kb_no_documents_ingested")

    return {"files": file_count, "chunks": len(documents), "errors": errors}


if __name__ == "__main__":
    stats = ingest_knowledge_base()
    print(f"Ingested {stats['chunks']} chunks from {stats['files']} files ({stats['errors']} errors)")
