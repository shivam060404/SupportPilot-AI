"""
src/observability/sampling.py
──────────────────────────────
Configurable payload sampling for production logging.

Controls which requests have their full payload logged (for privacy + cost).

Environment variables:
  LOG_SAMPLING_RATE=0.1    # Log 10% of requests at full detail (default: 1.0 in dev)
  ALWAYS_SAMPLE_ERRORS=true # Always log errors fully (default: true)
  REDACT_BEFORE_SAMPLE=true  # Apply PII redaction before sampling (default: true)
"""
from __future__ import annotations

import os
import random
from typing import Any, Dict, Optional

SAMPLING_RATE = float(os.getenv("LOG_SAMPLING_RATE", "1.0"))
ALWAYS_SAMPLE_ERRORS = os.getenv("ALWAYS_SAMPLE_ERRORS", "true").lower() == "true"
REDACT_BEFORE_SAMPLE = os.getenv("REDACT_BEFORE_SAMPLE", "true").lower() == "true"


def should_sample_full(is_error: bool = False) -> bool:
    """Determine if the current request should be fully logged."""
    if is_error and ALWAYS_SAMPLE_ERRORS:
        return True
    return random.random() < SAMPLING_RATE


def sample_payload(
    payload: Dict[str, Any],
    is_error: bool = False,
    redact: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Return the payload if it should be sampled, else None.

    Args:
        payload: The request/response payload dict.
        is_error: Whether this is an error event.
        redact: Whether to apply PII redaction before returning.

    Returns:
        Redacted payload dict if sampled, else None.
    """
    if not should_sample_full(is_error):
        return None

    if redact and REDACT_BEFORE_SAMPLE:
        from core.privacy.redactor import redact_dict
        return redact_dict(payload)

    return payload
