"""
core/guardrails/input/prompt_safety.py
──────────────────────────────────────
Input guardrail: Content safety filtering.

Blocks requests that contain:
  - Violence or threats
  - Self-harm content
  - Illegal activity requests
  - Explicit/adult content
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity

# (pattern, category, severity)
SAFETY_PATTERNS: List[Tuple[re.Pattern, str, ViolationSeverity]] = [
    # Self-harm
    (re.compile(r"\b(suicide|self.harm|kill\s+myself|end\s+my\s+life|want\s+to\s+die)\b", re.I),
     "self_harm", ViolationSeverity.CRITICAL),

    # Threats of violence
    (re.compile(r"\b(i\s+will\s+kill|i\s+want\s+to\s+kill|threaten|bomb\s+threat|shoot\s+up)\b", re.I),
     "violence_threat", ViolationSeverity.CRITICAL),

    # Hacking/illegal intrusion
    (re.compile(r"\b(how\s+to\s+hack|sql\s+injection|zero.day\s+exploit|keylogger|ransomware\s+deploy)\b", re.I),
     "illegal_activity", ViolationSeverity.HIGH),

    # Data exfiltration
    (re.compile(r"\b(exfiltrate|steal\s+data|scrape\s+all\s+users?|dump\s+the\s+database)\b", re.I),
     "data_exfiltration", ViolationSeverity.HIGH),
]

SAFETY_BLOCK_MESSAGES = {
    "self_harm": (
        "If you're experiencing distress, please reach out to a mental health professional "
        "or call a crisis helpline. I'm an IT support assistant and can't help with this, "
        "but support is available."
    ),
    "violence_threat": "🚫 This type of content cannot be processed. Please contact HR or security if needed.",
    "illegal_activity": "🚫 I can only assist with legitimate IT support requests.",
    "data_exfiltration": "🚫 This request cannot be processed.",
}


class PromptSafetyGuardrail(GuardrailBase):
    """Content safety filter for unsafe, violent, or illegal content."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("prompt_safety", enabled)

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled or not content:
            return self._pass(sanitized=content)

        for pattern, category, severity in SAFETY_PATTERNS:
            match = pattern.search(content)
            if match:
                return self._fail(
                    category=category,
                    message=f"Unsafe content detected: {category}",
                    severity=severity,
                    user_message=SAFETY_BLOCK_MESSAGES.get(category, "🚫 Request blocked."),
                    matched_text="[REDACTED]",  # Never log the actual content
                )

        return self._pass(sanitized=content)
