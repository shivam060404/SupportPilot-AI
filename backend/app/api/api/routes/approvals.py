"""
src/api/routes/approvals.py
───────────────────────────
Human-in-the-loop approval endpoints (spec §8/§12).

The LLM can only CREATE approval requests. Only humans — via these endpoints
or the UI panel — can APPROVE or REJECT them. Every decision is audit-logged.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    ApprovalItem,
    ApprovalListResponse,
    ApprovalDecisionRequest,
    ErrorResponse,
)
from src.persistence.repositories import ApprovalRepository, AuditLogRepository
from src.observability.logger import get_logger
from src.persistence.models import utc_now

log = get_logger(__name__)
router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _to_item(r) -> ApprovalItem:
    return ApprovalItem(
        id=r.id,
        session_id=r.session_id,
        action=r.action,
        target=r.target,
        rationale=r.rationale,
        status=r.status,
        requested_at=r.requested_at.isoformat() if r.requested_at else None,
        decided_at=r.decided_at.isoformat() if r.decided_at else None,
        executed_at=r.executed_at.isoformat() if r.executed_at else None,
    )


@router.get(
    "",
    response_model=ApprovalListResponse,
    summary="List approval requests (optionally filtered)",
)
async def list_approvals(
    status: Optional[str] = Query(default=None, description="PENDING | APPROVED | REJECTED | EXECUTED"),
    session_id: Optional[str] = Query(default=None),
) -> ApprovalListResponse:
    rows = ApprovalRepository.list_approvals(status=status, session_id=session_id)
    return ApprovalListResponse(approvals=[_to_item(r) for r in rows])


@router.get(
    "/{approval_id}",
    response_model=ApprovalItem,
    responses={404: {"model": ErrorResponse}},
    summary="Get one approval request",
)
async def get_approval(approval_id: str) -> ApprovalItem:
    row = ApprovalRepository.get_approval(approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return _to_item(row)


@router.post(
    "/{approval_id}/decide",
    response_model=ApprovalItem,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Approve or reject a pending approval (human decision)",
)
async def decide_approval(approval_id: str, body: ApprovalDecisionRequest) -> ApprovalItem:
    row = ApprovalRepository.get_approval(approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if row.status != "PENDING":
        raise HTTPException(status_code=409, detail=f"Approval already decided: {row.status}")

    updated = ApprovalRepository.decide(approval_id, body.decision)
    if not updated:
        raise HTTPException(status_code=409, detail="Approval could not be decided")

    log.info("approval_decided", approval_id=approval_id, decision=body.decision)
    return _to_item(updated)


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalItem,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Approve a pending approval",
)
async def approve_approval(approval_id: str) -> ApprovalItem:
    return await decide_approval(approval_id, ApprovalDecisionRequest(decision="APPROVED"))


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalItem,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Reject a pending approval",
)
async def reject_approval(approval_id: str) -> ApprovalItem:
    return await decide_approval(approval_id, ApprovalDecisionRequest(decision="REJECTED"))
