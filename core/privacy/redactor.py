"""
core/privacy/redactor.py
─────────────────────────
Central PII redaction engine used by logging middleware, guardrails, and
observability pipeline.

Thread-safe, reentrant. Applies all configured patterns and returns:
  - sanitized text with placeholders
  - list of detected PII types (for audit / metrics)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.privacy.pii_patterns import PATTERNS, PIIPattern, PIIType


@dataclass
class RedactionResult:
    original_length: int
    sanitized: str
    detections: List[PIIType] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return bool(self.detections)

    @property
    def redacted_count(self) -> int:
        return len(self.detections)


class PIIRedactor:
    """
    Scans text for PII using compiled regex patterns and replaces matches
    with type-appropriate placeholders.

    Usage:
        redactor = PIIRedactor()
        result = redactor.redact("My SSN is 123-45-6789")
        # result.sanitized == "My SSN is [REDACTED-SSN]"
    """

    def __init__(
        self,
        patterns: Optional[List[PIIPattern]] = None,
        min_confidence: float = 0.80,
    ) -> None:
        self._patterns = patterns or PATTERNS
        self._min_confidence = min_confidence
        # Filter by minimum confidence threshold
        self._active = [p for p in self._patterns if p.confidence >= min_confidence]

    def redact(self, text: str) -> RedactionResult:
        if not text or not isinstance(text, str):
            return RedactionResult(original_length=0, sanitized=text or "")

        sanitized = text
        detections: List[PIIType] = []

        for pattern in self._active:
            matches = pattern.pattern.findall(sanitized)
            if matches:
                detections.extend([pattern.pii_type] * len(matches))
                sanitized = pattern.pattern.sub(pattern.placeholder, sanitized)

        return RedactionResult(
            original_length=len(text),
            sanitized=sanitized,
            detections=detections,
        )

    def detect_only(self, text: str) -> List[PIIType]:
        """Return detected PII types without modifying text."""
        detections: List[PIIType] = []
        for pattern in self._active:
            if pattern.pattern.search(text):
                detections.append(pattern.pii_type)
        return detections

    def redact_dict(
        self,
        data: Dict[str, Any],
        keys_to_skip: Optional[List[str]] = None,
        depth: int = 0,
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """Recursively redact PII from dict values (for log payloads)."""
        if depth > max_depth:
            return data

        skip = set(keys_to_skip or [])
        result: Dict[str, Any] = {}

        for k, v in data.items():
            if k in skip:
                result[k] = v
            elif isinstance(v, str):
                result[k] = self.redact(v).sanitized
            elif isinstance(v, dict):
                result[k] = self.redact_dict(v, keys_to_skip, depth + 1, max_depth)
            elif isinstance(v, list):
                result[k] = [
                    self.redact(item).sanitized if isinstance(item, str)
                    else self.redact_dict(item, keys_to_skip, depth + 1, max_depth)
                    if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                result[k] = v

        return result


# ── Module-level singleton ────────────────────────────────────────────────────
_default_redactor: Optional[PIIRedactor] = None


def _get_redactor() -> PIIRedactor:
    global _default_redactor
    if _default_redactor is None:
        _default_redactor = PIIRedactor()
    return _default_redactor


def redact_text(text: str) -> RedactionResult:
    """Module-level convenience function."""
    return _get_redactor().redact(text)


def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Module-level convenience function."""
    return _get_redactor().redact_dict(data)
