"""
core/guardrails/output/content_moderation.py
─────────────────────────────────────────────
Output guardrail: Scans agent responses for unsafe content before returning to user.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity

# Patterns the agent should NEVER output
OUTPUT_SAFETY_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(I\s+hate|you\s+should\s+die|kill\s+yourself)\b", re.I), "hate_speech"),
    (re.compile(r"\b(my\s+system\s+prompt\s+is|my\s+instructions\s+say|I\s+was\s+told\s+to\s+keep)\b", re.I), "system_prompt_leak"),
    (re.compile(r"\b(gsk_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})\b"), "api_key_leak"),
]

FALLBACK_RESPONSE = (
    "I encountered an issue generating a safe response. "
    "Please rephrase your question or contact IT directly."
)


class ContentModerationGuardrail(GuardrailBase):
    """Scans outbound agent responses for policy violations."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("content_moderation", enabled)

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled or not content:
            return self._pass(sanitized=content)

        for pattern, category in OUTPUT_SAFETY_PATTERNS:
            if pattern.search(content):
                return self._fail(
                    category=f"output_{category}",
                    message=f"Output contains policy-violating content: {category}",
                    severity=ViolationSeverity.HIGH,
                    user_message=FALLBACK_RESPONSE,
                    sanitized=FALLBACK_RESPONSE,
                )

        return self._pass(sanitized=content)
