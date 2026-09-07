"""
src/mcp_server.py
─────────────────
A standard I/O (stdio) MCP server that provides mock Active Directory
capabilities. Built using the official `mcp` Python SDK.

Business logic lives in src/services/ad_directory.py so the guarded,
approval-checked execution path and this MCP server stay in sync.
"""
import sys
from pathlib import Path

# Make project-root imports work regardless of the parent's environment
# (MCP stdio clients spawn this process with a minimal environment).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.fastmcp import FastMCP

from src.services.ad_directory import check_account_status, get_manager_info, unlock_account

# Create a FastMCP server
mcp = FastMCP("Active Directory Server")


@mcp.tool()
def ad_check_account_status(email: str) -> str:
    """
    Check if an employee's Active Directory account is locked, active, or disabled.

    Args:
        email: The employee's company email address.
    """
    return check_account_status(email)


@mcp.tool()
def ad_get_manager_info(email: str) -> str:
    """
    Retrieve the manager's email address for a given employee to facilitate escalation approvals.

    Args:
        email: The employee's company email address.
    """
    return get_manager_info(email)


if __name__ == "__main__":
    # Run the server on standard I/O.
    # NOTE: unlock_account is intentionally NOT exposed as an MCP tool.
    # Sensitive actions may only run through execute_approved_action, which is
    # gated by a human approval record in the database (code-enforced guard).
    mcp.run(transport="stdio")
