"""
src/agents/escalation_agent.py
──────────────────────────────
Tier-2 Escalation Agent: handles account lockouts, managerial escalations and
other sensitive matters.

Tooling:
  • MCP stdio server (src/mcp_server.py) → read-only AD lookups
    (ad_check_account_status, ad_get_manager_info)
  • Local approval-gate tools (request_approval / execute_approved_action) →
    the ONLY path to privileged actions, verified against human approval
    records in the database. The unlock capability is deliberately NOT
    exposed via MCP.
"""
from typing import TYPE_CHECKING

import agent_framework as af
from agent_framework_openai import OpenAIChatClient

from src.agents.prompts_approval import ESCALATION_SYSTEM_PROMPT
from src.observability.logger import get_logger
from src.tools.approval import request_approval, execute_approved_action

if TYPE_CHECKING:
    from agent_framework import HistoryProvider

log = get_logger(__name__)


def create_escalation_agent(client: OpenAIChatClient, history_provider: "HistoryProvider") -> af.Agent:
    """Creates the Escalation Agent with MCP AD lookups + approval-gate tools."""

    ad_mcp_tool = af.MCPStdioTool(
        name="ad_mcp",
        command="python3",
        args=["src/mcp_server.py"],
        description="Active Directory MCP server for account status and manager lookup.",
    )

    agent = af.create_harness_agent(
        client=client,
        id="supportpilot-escalation",
        name="Tier 2 Specialist",
        agent_instructions=ESCALATION_SYSTEM_PROMPT,
        history_provider=history_provider,
        tools=[ad_mcp_tool, request_approval, execute_approved_action],
        loop_max_iterations=8,
    )

    return agent
