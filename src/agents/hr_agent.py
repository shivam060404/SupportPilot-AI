"""
src/agents/hr_agent.py
──────────────────────
HR Agent equipped with MCP tools.
"""
from typing import Optional
import uuid
import agent_framework as af
from agent_framework_openai import OpenAIChatClient
from config import get_settings
from src.observability.logger import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """
You are the SupportPilot HR Specialist.
You have access to an external HR system via MCP tools.
Use `get_employee_status` and `get_pto_balance` to answer HR questions.
Never invent data.
"""

def create_hr_agent(client: OpenAIChatClient, history_provider: af.HistoryProvider) -> af.Agent:
    """Creates the HR Agent with MCP Stdio Tool attached."""
    
    # We wire the MCP stdio tool that points to our local python server
    hr_mcp_tool = af.MCPStdioTool(
        name="hr_mcp",
        command="python3",
        args=["src/mcp_server.py"],
        description="HR System MCP server for employee data."
    )
    
    agent = af.create_harness_agent(
        client=client,
        id="supportpilot-hr",
        name="HR Specialist",
        agent_instructions=SYSTEM_PROMPT,
        history_provider=history_provider,
        tools=[hr_mcp_tool],
        loop_max_iterations=5,
    )
    
    return agent
