"""
src/rag/chunker.py
───────────────────
Semantic text chunker with overlap for high-quality RAG retrieval.

Features:
  - Recursive character splitting (respects sentence and paragraph boundaries)
  - Configurable chunk_size and chunk_overlap
  - Section-aware splitting (preserves markdown heading context)
  - Metadata enrichment per chunk (section_title, char_start, char_end)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Chunk:
    """A text chunk ready for embedding."""
    content: str
    metadata: Dict[str, str | int | float] = field(default_factory=dict)
    char_start: int = 0
    char_end: int = 0


# Split order: double newline → single newline → sentence boundary → space
_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " "]


def _split_recursive(
    text: str,
    chunk_size: int,
    separators: List[str],
    depth: int = 0,
) -> List[str]:
    """Recursively split text using progressively finer separators."""
    if len(text) <= chunk_size:
        return [text]

    sep = separators[depth] if depth < len(separators) else ""

    if not sep:
        # Hard split at character boundary
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(sep)
    result: List[str] = []
    current = ""

    for part in parts:
        candidate = current + (sep if current else "") + part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                result.append(current)
            if len(part) > chunk_size:
                # Part itself is too large — recurse with finer separator
                result.extend(_split_recursive(part, chunk_size, separators, depth + 1))
                current = ""
            else:
                current = part

    if current:
        result.append(current)

    return result


def _extract_section_title(text: str, position: int, full_text: str) -> Optional[str]:
    """Find the most recent markdown heading before the given position."""
    heading_pattern = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
    title = None
    for match in heading_pattern.finditer(full_text[:position]):
        title = match.group(2).strip()
    return title


class SemanticChunker:
    """
    Splits documents into overlapping chunks suitable for embedding + retrieval.

    Args:
        chunk_size: Target number of characters per chunk (default 512).
        chunk_overlap: Characters of overlap between consecutive chunks (default 64).
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(
        self,
        text: str,
        base_metadata: Optional[Dict] = None,
    ) -> List[Chunk]:
        """
        Split text into overlapping chunks with metadata.

        Args:
            text: Source document text.
            base_metadata: Metadata to attach to all chunks (e.g., title, category).

        Returns:
            List of Chunk objects.
        """
        if not text.strip():
            return []

        # First pass: rough split into candidate chunks
        raw_chunks = _split_recursive(text, self.chunk_size, _SEPARATORS)

        # Second pass: merge small chunks and apply overlap
        merged = self._apply_overlap(raw_chunks)

        chunks = []
        char_pos = 0

        for i, content in enumerate(merged):
            content = content.strip()
            if not content:
                continue

            char_start = text.find(content[:50], char_pos)
            if char_start == -1:
                char_start = char_pos
            char_end = char_start + len(content)
            char_pos = max(char_pos, char_start)

            meta = dict(base_metadata or {})
            meta["chunk_index"] = i
            meta["chunk_size"] = len(content)

            section = _extract_section_title(content, char_start, text)
            if section:
                meta["section_title"] = section

            chunks.append(Chunk(
                content=content,
                metadata=meta,
                char_start=char_start,
                char_end=char_end,
            ))

        return chunks

    def _apply_overlap(self, chunks: List[str]) -> List[str]:
        """Add overlap between consecutive chunks for context continuity."""
        if not chunks or self.chunk_overlap <= 0:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-self.chunk_overlap:]
            combined = prev_tail + " " + chunks[i]
            # Trim to max size if overlap pushes over limit
            if len(combined) > self.chunk_size + self.chunk_overlap:
                combined = chunks[i]
            result.append(combined)

        return result
