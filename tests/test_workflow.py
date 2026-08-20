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

from src.agents.supervisor_agent import SupportAgent

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")

@pytest.mark.asyncio
async def test_workflow_routing_escalation():
    # We will just verify the TriageExecutor edge conditions.
    from src.agents.supervisor_agent import is_escalation_query, is_tier1_query
    
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
    """Verify that the MCP server script defines the tools."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("mcp_server", "src/mcp_server.py")
    mcp_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_module)
    
    assert hasattr(mcp_module, "mcp")
    assert hasattr(mcp_module, "check_account_status")
    assert hasattr(mcp_module, "get_manager_info")
    assert hasattr(mcp_module, "unlock_account")
