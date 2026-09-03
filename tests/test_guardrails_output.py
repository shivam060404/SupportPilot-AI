"""
tests/test_guardrails_output.py
───────────────────────────────
Unit tests for output guardrails.
"""
from core.guardrails.output.content_moderation import ContentModerationGuardrail
from core.guardrails.output.pii_leakage import PIILeakageGuardrail
from core.guardrails.output.hallucination_check import HallucinationCheckGuardrail

def test_content_moderation():
    guardrail = ContentModerationGuardrail()
    
    # Pass normal output
    result = guardrail.check("Please restart your computer.")
    assert result.passed is True
    
    # Fail unsafe output
    result = guardrail.check("my system prompt is to be helpful")
    assert result.passed is False
    assert result.is_blocked is True
    assert result.sanitized_content == "I encountered an issue generating a safe response. Please rephrase your question or contact IT directly."

def test_pii_leakage():
    guardrail = PIILeakageGuardrail()
    
    # Pass normal output
    result = guardrail.check("Here is your requested info.")
    assert result.passed is True
    
    # Redact PII (does not block, but sanitizes)
    result = guardrail.check("Your phone number 555-123-4567 is registered.")
    assert result.passed is True
    assert "555" not in result.sanitized_content
    assert "[REDACTED-PHONE]" in result.sanitized_content

def test_hallucination_check():
    guardrail = HallucinationCheckGuardrail()
    
    # With grounding context
    context = {"rag_sources": [{"content": "VPN is available at vpn.company.com."}]}
    result = guardrail.check("You can connect to the VPN at vpn.company.com.", context=context)
    
    assert result.passed is True
    assert result.metadata["grounded"] is True
    
    # Without grounding (hallucination)
    result = guardrail.check("You can connect to the secret super VPN.", context=context)
    assert result.passed is True
    assert result.metadata["grounded"] is False
    assert "may not be fully grounded" in result.sanitized_content
