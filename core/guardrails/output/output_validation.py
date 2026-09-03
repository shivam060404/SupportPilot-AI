"""
core/guardrails/output/output_validation.py
────────────────────────────────────────────
Output guardrail: Structural validation of agent responses.

Ensures responses are:
  - Non-empty
  - Within reasonable length bounds
  - Not raw JSON/code dumps
  - Properly terminated
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity

MIN_RESPONSE_LENGTH = 10
MAX_RESPONSE_LENGTH = 8000

FALLBACK = "I'm sorry, I couldn't generate a proper response. Please try again or contact IT directly."


class OutputValidationGuardrail(GuardrailBase):
    """Validates the structure and format of agent responses."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("output_validation", enabled)

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled:
            return self._pass(sanitized=content)

        stripped = (content or "").strip()

        # Empty response
        if len(stripped) < MIN_RESPONSE_LENGTH:
            return self._fail(
                category="empty_response",
                message=f"Response is too short ({len(stripped)} chars)",
                severity=ViolationSeverity.MEDIUM,
                user_message=FALLBACK,
                sanitized=FALLBACK,
            )

        # Overly long response (truncate rather than block)
        if len(stripped) > MAX_RESPONSE_LENGTH:
            truncated = stripped[:MAX_RESPONSE_LENGTH] + "\n\n*[Response truncated for length.]*"
            return GuardrailResult(
                passed=True,
                sanitized_content=truncated,
                metadata={"truncated": True, "original_length": len(stripped)},
            )

        # Raw JSON dump detection (agent shouldn't output raw dicts)
        if stripped.startswith('{"') and stripped.endswith('}') and '"status"' in stripped:
            # This is a raw tool result echoed to user — replace it
            return GuardrailResult(
                passed=True,
                sanitized_content="I encountered an unexpected response format. Please try again.",
                metadata={"raw_json_detected": True},
            )

        return self._pass(sanitized=stripped)
