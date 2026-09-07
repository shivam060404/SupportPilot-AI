"""
core/guardrails/base.py
────────────────────────
Abstract base class for all guardrails.
Every guardrail implements check() returning a GuardrailViolation list.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ViolationSeverity(str, Enum):
    LOW = "low"           # Log and continue
    MEDIUM = "medium"     # Warn user, continue with sanitized content
    HIGH = "high"         # Block request, return error
    CRITICAL = "critical" # Block + escalate + alert


@dataclass
class GuardrailViolation:
    """A single policy violation detected by a guardrail."""
    guardrail: str
    severity: ViolationSeverity
    category: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    user_message: str = ""  # Safe message to show to user


@dataclass
class GuardrailResult:
    """Result of running a guardrail check."""
    passed: bool
    violations: List[GuardrailViolation] = field(default_factory=list)
    sanitized_content: Optional[str] = None  # PII-cleaned version of input
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        """True if any violation is HIGH or CRITICAL severity."""
        return any(
            v.severity in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL)
            for v in self.violations
        )

    @property
    def highest_severity(self) -> Optional[ViolationSeverity]:
        if not self.violations:
            return None
        order = [ViolationSeverity.CRITICAL, ViolationSeverity.HIGH,
                 ViolationSeverity.MEDIUM, ViolationSeverity.LOW]
        for sev in order:
            if any(v.severity == sev for v in self.violations):
                return sev
        return None

    def user_facing_block_message(self) -> str:
        """Return the safest user-facing message for a blocked request."""
        for v in self.violations:
            if v.severity in (ViolationSeverity.HIGH, ViolationSeverity.CRITICAL):
                if v.user_message:
                    return v.user_message
        return "Your request could not be processed due to policy restrictions. Please rephrase and try again."


class GuardrailBase(ABC):
    """Abstract base class for all input and output guardrails."""

    def __init__(self, name: str, enabled: bool = True) -> None:
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def check(self, content: str, context: Optional[Dict[str, Any]] = None) -> GuardrailResult:
        """
        Run the guardrail check.

        Args:
            content: Text to evaluate.
            context: Optional metadata (session_id, category, history, etc.).

        Returns:
            GuardrailResult with pass/fail, violations, and sanitized content.
        """
        ...

    def _pass(self, sanitized: Optional[str] = None, **metadata) -> GuardrailResult:
        return GuardrailResult(passed=True, sanitized_content=sanitized, metadata=metadata)

    def _fail(
        self,
        category: str,
        message: str,
        severity: ViolationSeverity = ViolationSeverity.HIGH,
        user_message: str = "",
        sanitized: Optional[str] = None,
        **details,
    ) -> GuardrailResult:
        violation = GuardrailViolation(
            guardrail=self.name,
            severity=severity,
            category=category,
            message=message,
            details=details,
            user_message=user_message,
        )
        return GuardrailResult(
            passed=False,
            violations=[violation],
            sanitized_content=sanitized,
        )
