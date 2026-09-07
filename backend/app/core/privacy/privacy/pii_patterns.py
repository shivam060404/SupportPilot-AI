"""
core/privacy/pii_patterns.py
─────────────────────────────
Centralized regex patterns for PII detection.

Covers common US and Indian formats. Patterns are compiled once at import time.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, NamedTuple, Pattern


class PIIType(str, Enum):
    EMAIL = "email"
    PHONE_US = "phone_us"
    PHONE_IN = "phone_in"
    SSN = "ssn"
    AADHAAR = "aadhaar"
    PAN = "pan"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    API_KEY = "api_key"
    JWT_TOKEN = "jwt_token"
    PASSWORD_LITERAL = "password_literal"
    EMPLOYEE_ID = "employee_id"


class PIIPattern(NamedTuple):
    pii_type: PIIType
    pattern: Pattern
    placeholder: str
    confidence: float  # 0.0–1.0


PATTERNS: List[PIIPattern] = [
    # Email
    PIIPattern(
        pii_type=PIIType.EMAIL,
        pattern=re.compile(
            r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
            re.IGNORECASE,
        ),
        placeholder="[REDACTED-EMAIL]",
        confidence=0.95,
    ),
    # US Phone
    PIIPattern(
        pii_type=PIIType.PHONE_US,
        pattern=re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
        placeholder="[REDACTED-PHONE]",
        confidence=0.85,
    ),
    # Indian Phone (10 digits starting with 6-9)
    PIIPattern(
        pii_type=PIIType.PHONE_IN,
        pattern=re.compile(r"\b(?:\+91[-.\s]?)?[6-9]\d{9}\b"),
        placeholder="[REDACTED-PHONE]",
        confidence=0.85,
    ),
    # US SSN
    PIIPattern(
        pii_type=PIIType.SSN,
        pattern=re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"),
        placeholder="[REDACTED-SSN]",
        confidence=0.95,
    ),
    # Credit Card (basic Luhn pattern check)
    PIIPattern(
        pii_type=PIIType.CREDIT_CARD,
        pattern=re.compile(
            r"\b(?:4\d{3}|5[1-5]\d{2}|6011|3[47]\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
        ),
        placeholder="[REDACTED-CC]",
        confidence=0.90,
    ),
    # Aadhaar (12-digit Indian national ID)
    PIIPattern(
        pii_type=PIIType.AADHAAR,
        pattern=re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}\b"),
        placeholder="[REDACTED-AADHAAR]",
        confidence=0.80,
    ),
    # PAN (Indian tax ID: AAAAA9999A format)
    PIIPattern(
        pii_type=PIIType.PAN,
        pattern=re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
        placeholder="[REDACTED-PAN]",
        confidence=0.90,
    ),
    # API Keys (Groq: gsk_, OpenAI: sk-)
    PIIPattern(
        pii_type=PIIType.API_KEY,
        pattern=re.compile(r"\b(gsk_|sk-|xoxb-|xoxp-)[A-Za-z0-9\-_]{16,}\b"),
        placeholder="[REDACTED-APIKEY]",
        confidence=0.98,
    ),
    # JWT tokens
    PIIPattern(
        pii_type=PIIType.JWT_TOKEN,
        pattern=re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
        placeholder="[REDACTED-TOKEN]",
        confidence=0.98,
    ),
    # Password literals (common patterns in text)
    PIIPattern(
        pii_type=PIIType.PASSWORD_LITERAL,
        pattern=re.compile(
            r"(?:password|passwd|pwd|secret)\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        placeholder="[REDACTED-PASSWORD]",
        confidence=0.85,
    ),
]

# Lookup by type for fast access
PATTERNS_BY_TYPE: Dict[PIIType, PIIPattern] = {p.pii_type: p for p in PATTERNS}
