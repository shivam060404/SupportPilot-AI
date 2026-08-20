"""
src/mcp_server.py
─────────────────
A standard I/O (stdio) MCP server that provides mock Active Directory capabilities.
Built using the official `mcp` Python SDK.
"""
from mcp.server.fastmcp import FastMCP

# Create a FastMCP server
mcp = FastMCP("Active Directory Server")

@mcp.tool()
def check_account_status(email: str) -> str:
    """
    Check if an employee's Active Directory account is locked, active, or disabled.
    
    Args:
        email: The employee's company email address.
    """
    email_lower = email.lower()
    if "locked" in email_lower:
        return f"Account for {email} is LOCKED due to multiple failed login attempts."
    elif "disabled" in email_lower:
        return f"Account for {email} is DISABLED."
    else:
        return f"Account for {email} is ACTIVE and in good standing."

@mcp.tool()
def get_manager_info(email: str) -> str:
    """
    Retrieve the manager's email address for a given employee to facilitate escalation approvals.
    
    Args:
        email: The employee's company email address.
    """
    if "ceo" in email.lower():
        return "No manager found. User is the CEO."
    return f"manager.of.{email.split('@')[0]}@company.com"

if __name__ == "__main__":
    # Run the server on standard I/O
    mcp.run(transport="stdio")
