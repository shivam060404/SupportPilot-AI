"""
src/mcp_server.py
─────────────────
A standard I/O (stdio) MCP server that provides mock HR capabilities.
Built using the official `mcp` Python SDK.
"""
from mcp.server.fastmcp import FastMCP

# Create a FastMCP server
mcp = FastMCP("HR Server")

@mcp.tool()
def get_employee_status(email: str) -> str:
    """
    Get the current employment status for a given employee email.
    
    Args:
        email: The employee's company email address.
    """
    if "jane" in email.lower():
        return f"Employee {email} is on leave."
    elif "ceo" in email.lower():
        return f"Employee {email} is active and is an executive."
    else:
        return f"Employee {email} is active and in good standing."

@mcp.tool()
def get_pto_balance(email: str) -> str:
    """
    Get the Paid Time Off (PTO) balance for an employee.
    
    Args:
        email: The employee's company email address.
    """
    if "jane" in email.lower():
        return "15 hours"
    elif "ceo" in email.lower():
        return "Unlimited"
    else:
        return "80 hours"

if __name__ == "__main__":
    # Run the server on standard I/O
    mcp.run(transport="stdio")
