"""
core/guardrails/input/pii_detector.py
──────────────────────────────────────
Input guardrail: Detects PII in user messages.

Behaviour:
  - Detects PII types (email, SSN, credit card, etc.)
  - Returns sanitized (redacted) version for use downstream
  - Severity MEDIUM: we scrub + continue (don't block the user for sharing their own email)
  - Severity HIGH: for highly sensitive data like SSN, credit card
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity, GuardrailViolation
from core.privacy.pii_patterns import PIIType
from core.privacy.redactor import PIIRedactor

# PII types that are HIGH severity (sensitive financial/government data)
HIGH_SEVERITY_PII = {PIIType.SSN, PIIType.CREDIT_CARD, PIIType.AADHAAR, PIIType.PAN}
# PII types that should not appear but are MEDIUM (we still scrub)
MEDIUM_SEVERITY_PII = {PIIType.PHONE_US, PIIType.PHONE_IN, PIIType.EMAIL}


class PIIDetectorGuardrail(GuardrailBase):
    """Detects PII in user input, redacts it, and flags violations."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("pii_detector", enabled)
        self._redactor = PIIRedactor()

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled or not content:
            return self._pass(sanitized=content)

        result = self._redactor.redact(content)

        if not result.has_pii:
            return self._pass(sanitized=content)

        # Determine highest severity PII found
        detected_set = set(result.detections)
        high_pii = detected_set & HIGH_SEVERITY_PII
        medium_pii = detected_set & MEDIUM_SEVERITY_PII

        violations = []

        if high_pii:
            violations.append(GuardrailViolation(
                guardrail=self.name,
                severity=ViolationSeverity.MEDIUM,  # Still scrub+continue, don't block
                category="pii_high_sensitivity",
                message=f"High-sensitivity PII detected: {[p.value for p in high_pii]}",
                details={"pii_types": [p.value for p in high_pii], "count": len(high_pii)},
                user_message=(
                    "⚠️ We detected sensitive personal information in your message. "
                    "It has been automatically redacted for your security. "
                    "Please avoid sharing SSN, Aadhaar, or card numbers in chat."
                ),
            ))

        if medium_pii and not high_pii:
            violations.append(GuardrailViolation(
                guardrail=self.name,
                severity=ViolationSeverity.LOW,
                category="pii_contact_info",
                message=f"Contact PII detected: {[p.value for p in medium_pii]}",
                details={"pii_types": [p.value for p in medium_pii], "count": len(medium_pii)},
                user_message="",  # Low severity: no user message needed
            ))

        return GuardrailResult(
            passed=True,  # PII detection never blocks; always scrub and continue
            violations=violations,
            sanitized_content=result.sanitized,
        )
