"""
src/tools/get_ticket_status.py
──────────────────────────────
Tool to retrieve an IT support ticket's status.
"""
import agent_framework as af
import json
from src.observability.tooltrace import traced_tool
from src.persistence.repositories import TicketRepository

@af.tool(name="get_ticket_status", description="Retrieve the status and details of an existing IT support ticket.")
@traced_tool("get_ticket_status")
def get_ticket_status(ticket_id: str) -> str:
    """
    Retrieve information about a specific ticket.
    
    Args:
        ticket_id: The unique ID of the ticket.
        
    Returns:
        JSON string containing the ticket details.
    """
    try:
        ticket = TicketRepository.get_ticket(ticket_id)
        if not ticket:
            return json.dumps({
                "status": "error",
                "message": f"Ticket {ticket_id} not found."
            })
            
        return json.dumps({
            "status": "success",
            "ticket_id": ticket.id,
            "ticket_status": ticket.status,
            "category": ticket.category,
            "priority": ticket.priority,
            "summary": ticket.summary
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to retrieve ticket: {str(e)}"
        })
