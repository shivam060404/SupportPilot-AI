"""
tests/test_workflow.py
─────────────────────
Workflow verification tests.
  - Test MCP server directly
  - Test Workflow routing
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
import agent_framework as af

from core.orchestration.agents.tier1_agent import SupportAgent
from core.orchestration.router import is_escalation_query, is_tier1_query

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")

@pytest.mark.asyncio
async def test_workflow_routing_escalation():
    # We will just verify the TriageExecutor edge conditions.
    from core.orchestration.router import is_escalation_query, is_tier1_query
    
    class MockMessage:
        def __init__(self, text: str):
            self.text = text
            
    # Escalation query
    msg_esc = MockMessage(text="Can you please unlock my account?")
    assert is_escalation_query([msg_esc]) == True
    assert is_tier1_query([msg_esc]) == False
    
    # IT Tier 1 query
    msg_it = MockMessage(text="My VPN is broken")
    assert is_escalation_query([msg_it]) == False
    assert is_tier1_query([msg_it]) == True

def test_mcp_server_exports():
    """Verify that the MCP server script defines the read-only AD tools."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("mcp_server", "src/mcp_server.py")
    mcp_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_module)

    assert hasattr(mcp_module, "mcp")
    assert hasattr(mcp_module, "ad_check_account_status")
    assert hasattr(mcp_module, "ad_get_manager_info")


def test_mcp_server_does_not_expose_unlock():
    """The sensitive unlock capability must NOT be reachable via MCP tools."""
    src_text = open("src/mcp_server.py").read()
    assert "@mcp.tool" in src_text
    assert 'def ad_check_account_status' in src_text
    assert 'def ad_get_manager_info' in src_text
    assert '@mcp.tool()\ndef unlock_account' not in src_text


# ── Routing conditions (deterministic pre-triage) ─────────────────────────────

class _M:
    def __init__(self, t): self.text = t


@pytest.mark.parametrize("text", [
    "My account is locked, please help",
    "Can you unlock my account?",
    "I need admin rights for this software install",
    "Who is my manager? I need their sign-off",
    "Please escalate this to someone who can help",
])
def test_escalation_routing(text):
    assert is_escalation_query([_M(text)]) is True
    assert is_tier1_query([_M(text)]) is False


@pytest.mark.parametrize("text", [
    "My VPN keeps disconnecting",
    "I forgot my password and cannot log in",
    "Wi-Fi is slow on my laptop",
    "I cannot access Jira today",
])
def test_tier1_routing(text):
    assert is_escalation_query([_M(text)]) is False
    assert is_tier1_query([_M(text)]) is True


def test_sticky_routing_on_open_approval(monkeypatch):
    """An unresolved approval keeps follow-ups in Tier 2 even without keywords."""
    from src.persistence.database import init_db
    from src.persistence.repositories import ApprovalRepository
    from src.observability.request_context import set_request_context, clear_request_context
    init_db()
    sid = "sticky-routing-session"
    req = ApprovalRepository.request_approval(session_id=sid, action="unlock_account", target="a@b.com")

    set_request_context(session_id=sid)
    try:
        assert is_escalation_query([_M("it is approved now, please go ahead")]) is True
        # Resolve it -> sticky signal disappears
        ApprovalRepository.decide(req.id, "APPROVED")
        ApprovalRepository.mark_executed(req.id)
        assert is_escalation_query([_M("thanks, anything else?")]) is False
    finally:
        clear_request_context()
