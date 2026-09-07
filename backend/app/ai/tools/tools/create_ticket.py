"""
src/tools/create_ticket.py
──────────────────────────
Tool to create an IT support ticket.
"""
import agent_framework as af
import json
from src.observability.tooltrace import traced_tool
from src.persistence.repositories import TicketRepository

@af.tool(name="create_ticket", description="Create a new IT support ticket. Use this when an issue cannot be resolved immediately and requires IT staff intervention. Priority must be LOW, MEDIUM, HIGH or CRITICAL.")
@traced_tool("create_ticket")
def create_ticket(summary: str, category: str, priority: str = "MEDIUM") -> str:
    """
    Create a new support ticket in the system.
    
    Args:
        summary: A brief description of the issue.
        category: The category of the issue (e.g., 'VPN', 'Password', 'WiFi').
        priority: The priority level ('LOW', 'MEDIUM', 'HIGH').
        
    Returns:
        JSON string containing the new ticket ID and status.
    """
    try:
        ticket = TicketRepository.create_ticket(
            summary=summary,
            category=category,
            priority=priority
        )
        return json.dumps({
            "status": "success",
            "ticket_id": ticket.id,
            "message": f"Ticket {ticket.id} created successfully."
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to create ticket: {str(e)}"
        })
