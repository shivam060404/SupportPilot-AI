"""
core/guardrails/input/contextual_compliance.py
───────────────────────────────────────────────
Input guardrail: Domain-scope enforcement.

SupportPilot AI is an IT Support agent. Requests outside this scope
(medical advice, legal questions, financial advice, personal relationship
advice, etc.) are politely declined.

Severity MEDIUM: user gets redirected, not blocked with an error.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity

# (pattern, topic_name, redirect_message)
OUT_OF_SCOPE_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"\b(diagnose|symptoms|medicine|prescription|dosage|treatment|medical\s+advice|doctor)\b", re.I),
        "medical_advice",
        "I'm an IT support assistant and can't provide medical advice. Please consult a healthcare professional.",
    ),
    (
        re.compile(r"\b(legal\s+advice|lawsuit|sue|attorney|lawyer|court\s+case|divorce)\b", re.I),
        "legal_advice",
        "I'm an IT support assistant and can't provide legal advice. Please consult a qualified lawyer.",
    ),
    (
        re.compile(r"\b(invest|stock\s+market|crypto|bitcoin|financial\s+advice|tax\s+advice|loan)\b", re.I),
        "financial_advice",
        "I'm an IT support assistant and can't provide financial or investment advice.",
    ),
    (
        re.compile(r"\b(relationship|breakup|girlfriend|boyfriend|marriage|personal\s+problem)\b", re.I),
        "personal_relationship",
        "I'm an IT support assistant focused on workplace technology. For personal matters, I'm afraid I can't help.",
    ),
    (
        re.compile(r"\b(write\s+my\s+essay|homework|assignment|exam\s+answer|academic)\b", re.I),
        "academic_assistance",
        "I'm an IT support assistant and can only help with work-related technology issues.",
    ),
    (
        re.compile(r"\b(cook|recipe|restaurant|food|diet|workout|exercise)\b", re.I),
        "lifestyle",
        "I'm an IT support assistant! I can help with VPN, passwords, Wi-Fi, applications, and other IT issues.",
    ),
]


class ContextualComplianceGuardrail(GuardrailBase):
    """Enforces IT domain scope — redirects off-topic requests."""

    def __init__(self, enabled: bool = True) -> None:
        super().__init__("contextual_compliance", enabled)

    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        if not self.enabled or not content:
            return self._pass(sanitized=content)

        for pattern, topic, redirect_msg in OUT_OF_SCOPE_PATTERNS:
            if pattern.search(content):
                # MEDIUM severity: we respond with a redirect, not a block error
                return self._fail(
                    category="out_of_scope",
                    message=f"Request is outside IT support domain: {topic}",
                    severity=ViolationSeverity.MEDIUM,
                    user_message=redirect_msg,
                    topic=topic,
                )

        return self._pass(sanitized=content)
