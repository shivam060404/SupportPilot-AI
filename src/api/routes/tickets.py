"""
src/api/routes/tickets.py
─────────────────────────
Endpoints for ticket management (list, create, get).
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import TicketCreateRequest, TicketResponse, ErrorResponse
from src.persistence.repositories import TicketRepository

router = APIRouter(prefix="/tickets", tags=["Tickets"])


def _to_response(t) -> TicketResponse:
    return TicketResponse(
        id=t.id,
        status=t.status,
        category=t.category,
        priority=t.priority,
        summary=t.summary,
        created_at=t.created_at.isoformat() if t.created_at else "",
        updated_at=t.updated_at.isoformat() if t.updated_at else "",
    )


@router.get(
    "",
    response_model=list[TicketResponse],
    summary="List tickets (optionally by status)",
)
async def list_tickets(
    status: Optional[str] = Query(default=None, description="OPEN | IN_PROGRESS | RESOLVED"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TicketResponse]:
    return [_to_response(t) for t in TicketRepository.list_tickets(status=status, limit=limit)]


@router.post(
    "",
    response_model=TicketResponse,
    status_code=201,
    responses={422: {"model": ErrorResponse}},
    summary="Create a ticket directly (IT staff)",
)
async def create_ticket(body: TicketCreateRequest) -> TicketResponse:
    try:
        ticket = TicketRepository.create_ticket(
            summary=body.summary,
            category=body.category,
            priority=body.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _to_response(ticket)


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
    return _to_response(ticket)
