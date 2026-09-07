"""
tests/test_pii_redaction.py
───────────────────────────
Tests for the PII redactor.
"""
from core.privacy.redactor import PIIRedactor

def test_pii_redaction():
    redactor = PIIRedactor()
    
    # Test Email Redaction
    res = redactor.redact("Contact me at user@example.com.")
    assert "user@example.com" not in res.sanitized
    assert "[REDACTED-EMAIL]" in res.sanitized
    
    # Test SSN Redaction
    res = redactor.redact("My SSN is 123-45-6789.")
    assert "123-45-6789" not in res.sanitized
    assert "[REDACTED-SSN]" in res.sanitized

    # Test Credit Card Redaction
    res = redactor.redact("My CC is 4532 1111 1111 1111.")
    assert "4532" not in res.sanitized
    assert "[REDACTED-CC]" in res.sanitized
