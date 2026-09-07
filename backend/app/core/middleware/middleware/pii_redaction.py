"""
core/middleware/pii_redaction.py
─────────────────────────────────
Structlog processor: redacts PII from log event dicts before writing.

Works alongside SecretsFilterProcessor. Applied as a structlog processor
so ALL log output (including tool traces) is automatically scrubbed.
"""
from __future__ import annotations

from typing import Any, MutableMapping

from core.privacy.redactor import PIIRedactor

_redactor = PIIRedactor()


class PIIRedactionProcessor:
    """
    Structlog processor: strips PII from string log values.

    Usage in structlog config:
        processors = [..., PIIRedactionProcessor(), renderer]
    """
    def __call__(
        self,
        logger: Any,
        method: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        for key in list(event_dict.keys()):
            val = event_dict[key]
            if isinstance(val, str) and len(val) > 5:
                event_dict[key] = _redactor.redact(val).sanitized
            elif isinstance(val, dict):
                event_dict[key] = _redactor.redact_dict(val)
        return event_dict
