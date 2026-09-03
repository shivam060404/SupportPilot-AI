"""core/privacy — PII detection, redaction, retention policies."""
from .redactor import PIIRedactor, redact_text, redact_dict
from .pii_patterns import PIIType, PATTERNS

__all__ = ["PIIRedactor", "redact_text", "redact_dict", "PIIType", "PATTERNS"]
