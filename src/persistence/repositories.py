"""
src/persistence/repositories.py
───────────────────────────────
CRUD operations for tickets, approvals, audit logs and chat sessions.
All authorization / guardrail checks live here or above — never inside the LLM.
"""
from typing import Dict, Any, List, Optional

from src.persistence.database import SessionLocal
from src.persistence.models import Ticket, AuditLog, SessionMessage, ApprovalRequest, utc_now
from src.observability.logger import get_logger

log = get_logger(__name__)

VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class TicketRepository:

    @staticmethod
    def create_ticket(summary: str, category: str, priority: str = "MEDIUM") -> Ticket:
        summary = (summary or "").strip()
        category = (category or "").strip()
        priority = (priority or "MEDIUM").strip().upper()

        if not summary:
            raise ValueError("Ticket summary must not be empty.")
        if not category:
            raise ValueError("Ticket category must not be empty.")
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'. Allowed: {sorted(VALID_PRIORITIES)}")

        with SessionLocal() as db:
            ticket = Ticket(
                summary=summary,
                category=category,
                priority=priority,
                status="OPEN"
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            detached = TicketRepository._detached_copy(ticket)

        AuditLogRepository.log_action(
            action="ticket_created",
            details={
                "ticket_id": detached.id,
                "category": detached.category,
                "priority": detached.priority,
                "summary": detached.summary,
            },
        )
        return detached

    @staticmethod
    def get_ticket(ticket_id: str) -> Optional[Ticket]:
        with SessionLocal() as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return None
            return TicketRepository._detached_copy(ticket)

    @staticmethod
    def list_tickets(status: Optional[str] = None, limit: int = 50) -> List[Ticket]:
        with SessionLocal() as db:
            query = db.query(Ticket).order_by(Ticket.created_at.desc())
            if status:
                query = query.filter(Ticket.status == status.upper())
            tickets = query.limit(max(1, min(limit, 200))).all()
            return [TicketRepository._detached_copy(t) for t in tickets]

    @staticmethod
    def _detached_copy(t: Ticket) -> Ticket:
        return Ticket(
            id=t.id,
            status=t.status,
            category=t.category,
            priority=t.priority,
            summary=t.summary,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )


class ApprovalRepository:
    """Persistence for the human-in-the-loop approval gate."""

    @staticmethod
    def request_approval(
        session_id: str, action: str, target: str, rationale: str = ""
    ) -> ApprovalRequest:
        with SessionLocal() as db:
            req = ApprovalRequest(
                session_id=session_id,
                action=(action or "").strip(),
                target=(target or "").strip(),
                rationale=(rationale or "").strip() or None,
                status="PENDING",
            )
            db.add(req)
            db.commit()
            db.refresh(req)
            return ApprovalRepository._detached_copy(req)

    @staticmethod
    def get_approval(approval_id: str) -> Optional[ApprovalRequest]:
        with SessionLocal() as db:
            req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
            return ApprovalRepository._detached_copy(req) if req else None

    @staticmethod
    def decide(approval_id: str, decision: str) -> Optional[ApprovalRequest]:
        """Approve or reject a PENDING request. Returns updated record or None."""
        decision = decision.strip().upper()
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("Decision must be APPROVED or REJECTED.")

        with SessionLocal() as db:
            req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
            if not req or req.status != "PENDING":
                return None
            req.status = decision
            req.decided_at = utc_now()
            db.commit()
            db.refresh(req)
            detached = ApprovalRepository._detached_copy(req)

        AuditLogRepository.log_action(
            action=f"approval_{decision.lower()}",
            details={"approval_id": approval_id, "action": detached.action, "target": detached.target},
            session_id=detached.session_id,
        )
        return detached

    @staticmethod
    def mark_executed(approval_id: str) -> bool:
        with SessionLocal() as db:
            req = db.query(ApprovalRequest).filter(ApprovalRequest.id == approval_id).first()
            if not req or req.status != "APPROVED":
                return False
            req.status = "EXECUTED"
            req.executed_at = utc_now()
            db.commit()
            return True

    @staticmethod
    def list_approvals(
        status: Optional[str] = None, session_id: Optional[str] = None, limit: int = 50
    ) -> List[ApprovalRequest]:
        with SessionLocal() as db:
            query = db.query(ApprovalRequest).order_by(ApprovalRequest.requested_at.desc())
            if status:
                query = query.filter(ApprovalRequest.status == status.upper())
            if session_id:
                query = query.filter(ApprovalRequest.session_id == session_id)
            rows = query.limit(max(1, min(limit, 200))).all()
            return [ApprovalRepository._detached_copy(r) for r in rows]

    @staticmethod
    def _detached_copy(r: ApprovalRequest) -> ApprovalRequest:
        return ApprovalRequest(
            id=r.id,
            session_id=r.session_id,
            action=r.action,
            target=r.target,
            rationale=r.rationale,
            status=r.status,
            requested_at=r.requested_at,
            decided_at=r.decided_at,
            executed_at=r.executed_at,
        )


class AuditLogRepository:

    @staticmethod
    def log_action(action: str, details: Dict[str, Any], session_id: Optional[str] = None) -> AuditLog:
        try:
            with SessionLocal() as db:
                log_entry = AuditLog(
                    action=action,
                    details=details,
                    session_id=session_id
                )
                db.add(log_entry)
                db.commit()
                db.refresh(log_entry)
                return log_entry
        except Exception as exc:  # auditing must never break the main flow
            log.error("audit_log_failed", action=action, error=str(exc))
            return None


class SessionRepository:
    @staticmethod
    def save_messages(session_id: str, messages_json: list[str]) -> None:
        """Append serialized messages for a session.

        Idempotent per exact JSON payload: a message already persisted for this
        session is skipped, so retried/duplicate saves cannot grow history.
        """
        from src.persistence.models import SessionMessage
        if not messages_json:
            return
        with SessionLocal() as db:
            existing = {
                row.message_json
                for row in db.query(SessionMessage.message_json)
                .filter(SessionMessage.session_id == session_id)
                .all()
            }
            fresh = [m for m in messages_json if m not in existing]
            for msg_json in fresh:
                db.add(SessionMessage(session_id=session_id, message_json=msg_json))
            if fresh:
                db.commit()

    @staticmethod
    def get_messages(session_id: str) -> list[str]:
        """Retrieve serialized messages for a session, ordered by creation time."""
        from src.persistence.models import SessionMessage
        with SessionLocal() as db:
            rows = (
                db.query(SessionMessage)
                .filter(SessionMessage.session_id == session_id)
                .order_by(SessionMessage.created_at, SessionMessage.id)
                .all()
            )
            return [row.message_json for row in rows]
