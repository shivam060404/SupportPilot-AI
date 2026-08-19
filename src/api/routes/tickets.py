"""
src/api/routes/tickets.py
─────────────────────────
Endpoints for ticket management.
"""
from fastapi import APIRouter, HTTPException
from src.persistence.repositories import TicketRepository
from src.api.schemas import TicketResponse, ErrorResponse

router = APIRouter(prefix="/tickets", tags=["Tickets"])

@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get ticket details",
)
async def get_ticket(ticket_id: str) -> TicketResponse:
    ticket = TicketRepository.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    return TicketResponse(
        id=ticket.id,
        status=ticket.status,
        category=ticket.category,
        priority=ticket.priority,
        summary=ticket.summary,
        created_at=ticket.created_at.isoformat() if ticket.created_at else "",
        updated_at=ticket.updated_at.isoformat() if ticket.updated_at else ""
    )
