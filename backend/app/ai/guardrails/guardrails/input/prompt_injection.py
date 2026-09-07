"""
core/guardrails/input/prompt_injection.py
──────────────────────────────────────────
Input guardrail: Prompt injection and jailbreak detection.

Detects attempts to:
  - Override the system prompt
  - Extract the system prompt
  - Jailbreak the agent identity
  - Use indirect injection via pasted content
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity

# ── Injection patterns ────────────────────────────────────────────────────────
# Each entry: (pattern, description, severity)
INJECTION_PATTERNS: List[Tuple[re.Pattern, str, ViolationSeverity]] = [
    # Direct override attempts
    (re.compile(r"\bignore\b.{0,30}\b(previous|prior|above|all)\b.{0,30}\b(instruction|prompt|rule|context)", re.I),
     "Instruction override attempt", ViolationSeverity.HIGH),

    # System prompt extraction
    (re.compile(r"\b(reveal|show|print|display|output|tell me|what is|repeat)\b.{0,30}\b(system\s*prompt|instructions|context|rules)", re.I),
     "System prompt extraction attempt", ViolationSeverity.HIGH),

    # Identity jailbreak
    (re.compile(r"\byou\s+are\s+now\b.{0,50}\b(dan|jailbreak|unrestricted|free\s+mode|no\s+limit)", re.I),
     "Identity jailbreak attempt", ViolationSeverity.CRITICAL),

    # "Pretend you are" patterns
    (re.compile(r"\b(pretend|imagine|roleplay|act|behave)\b.{0,20}\b(you\s+are|as\s+if|like\s+you\s+are)\b.{0,30}\b(not|no longer|without restriction)", re.I),
     "Role jailbreak attempt", ViolationSeverity.HIGH),

    # DAN-style jailbreaks
    (re.compile(r"\b(DAN|developer\s+mode|jailbreak\s+mode|sudo\s+mode|god\s+mode)\b", re.I),
     "Known jailbreak pattern", ViolationSeverity.CRITICAL),

    # Prompt delimiter injection
    (re.compile(r"(---+\s*(SYSTEM|HUMAN|ASSISTANT|USER)\s*---+|<\|im_start\|>|<\|im_end\|>)", re.I),
     "Prompt delimiter injection", ViolationSeverity.HIGH),

    # "Disregard" patterns
    (re.compile(r"\b(disregard|forget|bypass|override|circumvent|disable)\b.{0,30}\b(safety|filter|guardrail|instruction|rule|policy)", re.I),
     "Safety bypass attempt", ViolationSeverity.HIGH),

    # Indirect injection via "the document says"
    (re.compile(r"\b(above\s+text|document\s+says?|article\s+says?|following\s+instructions?)\s*[:]\s*(ignore|disable|override)", re.I),
     "Indirect prompt injection", ViolationSeverity.HIGH),
]

BLOCK_USER_MESSAGE = (
    "🚫 Your message contains patterns that could compromise system security. "
    "Please describe your IT issue directly and I'll be happy to help."
)


class PromptInjectionGuardrail(GuardrailBase):
    """Detects and blocks prompt injection and jailbreak attempts."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("prompt_injection", enabled)

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled or not content:
            return self._pass(sanitized=content)

        for pattern, description, severity in INJECTION_PATTERNS:
            match = pattern.search(content)
            if match:
                return self._fail(
                    category="prompt_injection",
                    message=f"{description}: matched '{match.group(0)[:80]}'",
                    severity=severity,
                    user_message=BLOCK_USER_MESSAGE,
                    matched_pattern=pattern.pattern[:100],
                    matched_text=match.group(0)[:80],
                )

        return self._pass(sanitized=content)
