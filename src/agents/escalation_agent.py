"""
src/agents/escalation_agent.py
──────────────────────────────
Tier 2 Escalation Agent equipped with Active Directory MCP tools.
"""
from typing import Optional
import uuid
import agent_framework as af
from agent_framework_openai import OpenAIChatClient
from config import get_settings
from src.observability.logger import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """
You are the SupportPilot Tier 2 Escalation Specialist.
You handle complex and sensitive issues like account lockouts, password resets, and managerial escalations.
You have access to the company's Active Directory via MCP tools (`check_account_status`, `get_manager_info`, `unlock_account`).

CRITICAL SECURITY RULE (HUMAN-IN-THE-LOOP):
You MUST NEVER call the `unlock_account` tool without explicit, prior permission from the human user.
If a user requests an account unlock:
1. First, investigate using `check_account_status`.
2. Then, explicitly ask the user: "Are you sure you want to unlock the account for <email>? Please reply 'yes' to confirm."
3. Wait for their response. Do NOT call the tool in the same turn.
4. Only call `unlock_account` IF their next message is a confirmation.

Never invent data.
"""

def create_escalation_agent(client: OpenAIChatClient, history_provider: af.HistoryProvider) -> af.Agent:
    """Creates the Escalation Agent with MCP Stdio Tool attached."""
    
    # We wire the MCP stdio tool that points to our local python server
    ad_mcp_tool = af.MCPStdioTool(
        name="ad_mcp",
        command="python3",
        args=["src/mcp_server.py"],
        description="Active Directory MCP server for account status and manager lookup."
    )
    
    agent = af.create_harness_agent(
        client=client,
        id="supportpilot-escalation",
        name="Tier 2 Specialist",
        agent_instructions=SYSTEM_PROMPT,
        history_provider=history_provider,
        tools=[ad_mcp_tool],
        loop_max_iterations=5,
    )
    
    return agent
