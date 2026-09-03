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

import sys

import agent_framework as af
from agent_framework_openai import OpenAIChatCompletionClient

from core.orchestration.prompts.tier2_prompt import ESCALATION_SYSTEM_PROMPT
from src.observability.logger import get_logger
from src.tools.approval import request_approval, execute_approved_action

if TYPE_CHECKING:
    from agent_framework import HistoryProvider

log = get_logger(__name__)


def create_escalation_agent(client: OpenAIChatCompletionClient, history_provider: "HistoryProvider") -> af.Agent:
    """Creates the Escalation Agent with MCP AD lookups + approval-gate tools."""

    ad_mcp_tool = af.MCPStdioTool(
        name="ad_mcp",
        # Use the same interpreter that runs the app so the `mcp` package
        # is guaranteed to be importable (venv locally, /app python in Docker).
        command=sys.executable,
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
        disable_web_search=True,   # Groq rejects web_search_options
        disable_file_memory=True,  # SQLite history provider is the single source of truth
        disable_todo=True,         # Groq rejects malformed calls to built-in todo tools
        disable_mode=True,
    )

    return agent
