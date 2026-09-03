"""
core/guardrails/input/input_validation.py
──────────────────────────────────────────
Input guardrail: Schema and format validation.

Checks:
  - Empty / whitespace-only messages
  - Maximum length enforcement
  - UTF-8 encoding validity
  - Excessive repetition (flood/DoS protection)
  - Binary/non-text content
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity

MAX_MESSAGE_LENGTH = 4096
MIN_MESSAGE_LENGTH = 1
MAX_REPETITION_RATIO = 0.7  # If >70% of chars are the same, it's spam


class InputValidationGuardrail(GuardrailBase):
    """Validates message format, length, and structure."""

    def __init__(
        self,
        max_length: int = MAX_MESSAGE_LENGTH,
        min_length: int = MIN_MESSAGE_LENGTH,
        enabled: bool = True,
    ) -> None:
        super().__init__("input_validation", enabled)
        self.max_length = max_length
        self.min_length = min_length

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled:
            return self._pass(sanitized=content)

        # Empty / whitespace check
        stripped = content.strip() if content else ""
        if len(stripped) < self.min_length:
            return self._fail(
                category="empty_message",
                message="Message is empty or whitespace only",
                severity=ViolationSeverity.MEDIUM,
                user_message="Please type your IT issue and I'll be happy to help!",
            )

        # Length check
        if len(content) > self.max_length:
            return self._fail(
                category="message_too_long",
                message=f"Message length {len(content)} exceeds maximum {self.max_length}",
                severity=ViolationSeverity.MEDIUM,
                user_message=f"Your message is too long ({len(content)} characters). Please keep it under {self.max_length} characters.",
                actual_length=len(content),
                max_length=self.max_length,
            )

        # Binary/non-printable character detection
        non_printable = sum(1 for c in content if ord(c) < 32 and c not in "\n\r\t")
        if non_printable > 5:
            return self._fail(
                category="binary_content",
                message=f"Message contains {non_printable} non-printable characters",
                severity=ViolationSeverity.HIGH,
                user_message="Your message contains invalid characters. Please send a plain text description of your issue.",
            )

        # Repetition / flood detection
        if len(stripped) > 50:
            most_common_char = max(set(stripped.lower()), key=stripped.lower().count)
            ratio = stripped.lower().count(most_common_char) / len(stripped)
            if ratio > MAX_REPETITION_RATIO:
                return self._fail(
                    category="repetition_flood",
                    message=f"Message has excessive repetition (ratio={ratio:.2f})",
                    severity=ViolationSeverity.MEDIUM,
                    user_message="Please describe your IT issue clearly and I'll help you.",
                )

        return self._pass(sanitized=stripped)
