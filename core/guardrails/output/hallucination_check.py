"""
core/guardrails/output/hallucination_check.py
──────────────────────────────────────────────
Output guardrail: Grounding verification.

Compares agent response against retrieved RAG sources. If the response
makes specific factual claims not present in any source, it adds a
confidence warning rather than blocking.

Note: Full semantic hallucination detection requires an LLM judge, which
adds latency. This implementation uses a fast lexical overlap check
(suitable for MVP). Upgrade path: replace with an async LLM-as-judge call.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity

# Minimum word overlap ratio to consider response grounded
GROUNDING_THRESHOLD = 0.15
LOW_CONFIDENCE_THRESHOLD = 0.05

UNGROUNDED_DISCLAIMER = (
    "\n\n⚠️ *Note: This response may not be fully grounded in official documentation. "
    "Please verify with your IT team.*"
)


def _word_overlap_ratio(text1: str, text2: str) -> float:
    """Simple word-level overlap ratio between two texts."""
    words1 = set(re.findall(r'\b\w{4,}\b', text1.lower()))  # 4+ char words
    words2 = set(re.findall(r'\b\w{4,}\b', text2.lower()))
    if not words1 or not words2:
        return 0.0
    overlap = words1 & words2
    return len(overlap) / min(len(words1), len(words2))


class HallucinationCheckGuardrail(GuardrailBase):
    """Checks if agent response is grounded in retrieved sources."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("hallucination_check", enabled)

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled or not content:
            return self._pass(sanitized=content)

        # Sources are injected into context by the RAG tool
        sources: List[Dict[str, Any]] = (context or {}).get("rag_sources", [])

        # If no sources were retrieved, we can't check — pass with metadata
        if not sources:
            return GuardrailResult(
                passed=True,
                sanitized_content=content,
                metadata={"grounded": None, "reason": "no_sources_retrieved"},
            )

        # Compute overlap against each source
        combined_sources = " ".join(s.get("content", "") for s in sources)
        overlap = _word_overlap_ratio(content, combined_sources)

        if overlap < LOW_CONFIDENCE_THRESHOLD:
            # Very low overlap: append disclaimer
            return GuardrailResult(
                passed=True,
                violations=[],
                sanitized_content=content + UNGROUNDED_DISCLAIMER,
                metadata={
                    "grounded": False,
                    "overlap_ratio": round(overlap, 3),
                    "disclaimer_appended": True,
                },
            )

        return GuardrailResult(
            passed=True,
            sanitized_content=content,
            metadata={
                "grounded": overlap >= GROUNDING_THRESHOLD,
                "overlap_ratio": round(overlap, 3),
            },
        )
