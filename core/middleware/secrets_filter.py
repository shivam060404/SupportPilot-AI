"""
core/middleware/secrets_filter.py
──────────────────────────────────
Structlog processor that scrubs API keys, tokens, and secrets from log records
before they are written to any output stream.

Add to structlog's processor chain:
    processors=[..., SecretsFilterProcessor(), ...]
"""
from __future__ import annotations

import re
from typing import Any, MutableMapping

# Patterns for common secret formats
_SECRET_PATTERNS = [
    re.compile(r"\bgsk_[A-Za-z0-9\-_]{16,}\b"),           # Groq API key
    re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}\b"),             # OpenAI API key
    re.compile(r"\bxox[bpoa]-[A-Za-z0-9\-]{24,}\b"),       # Slack token
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),                 # GitHub PAT
    re.compile(r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), # JWT
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),           # Base64 secrets (long)
    re.compile(r"(?i)(password|passwd|secret|token|api_key|apikey)\s*[:=]\s*\S+"),
]

_PLACEHOLDER = "***REDACTED***"


def _scrub_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(_PLACEHOLDER, value)
    return value


def _scrub_dict(record: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key in list(record.keys()):
        val = record[key]
        if isinstance(val, str):
            record[key] = _scrub_value(val)
        elif isinstance(val, dict):
            _scrub_dict(val)
    return record


class SecretsFilterProcessor:
    """
    Structlog processor: removes secrets from log event dicts.

    Usage in structlog config:
        processors = [..., SecretsFilterProcessor(), renderer]
    """
    def __call__(
        self,
        logger: Any,
        method: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        return _scrub_dict(event_dict)
