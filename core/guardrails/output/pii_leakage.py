"""
core/guardrails/output/pii_leakage.py
──────────────────────────────────────
Output guardrail: Prevents PII from leaking in agent responses.

The LLM might echo back user-provided PII from context. This guardrail
scrubs it from the outbound response.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity
from core.privacy.pii_patterns import PIIType
from core.privacy.redactor import PIIRedactor

# For output we always redact and continue (never block a helpful response)
HIGH_SENSITIVITY_OUTPUT = {PIIType.SSN, PIIType.CREDIT_CARD, PIIType.AADHAAR}


class PIILeakageGuardrail(GuardrailBase):
    """Scans and sanitizes PII from agent responses."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("pii_leakage", enabled)
        self._redactor = PIIRedactor()

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled or not content:
            return self._pass(sanitized=content)

        result = self._redactor.redact(content)

        if not result.has_pii:
            return self._pass(sanitized=content)

        detected_set = set(result.detections)
        severity = (
            ViolationSeverity.HIGH
            if detected_set & HIGH_SENSITIVITY_OUTPUT
            else ViolationSeverity.MEDIUM
        )

        return GuardrailResult(
            passed=True,  # Always pass but with sanitized content
            violations=[],
            sanitized_content=result.sanitized,
            metadata={
                "pii_redacted": True,
                "pii_types": [p.value for p in detected_set],
                "severity": severity.value,
            },
        )
