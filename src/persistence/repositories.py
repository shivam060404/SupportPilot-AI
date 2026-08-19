"""
src/persistence/repositories.py
───────────────────────────────
CRUD operations for tickets and audit logs.
"""
from typing import Dict, Any, Optional
from src.persistence.database import SessionLocal
from src.persistence.models import Ticket, AuditLog


class TicketRepository:
    
    @staticmethod
    def create_ticket(summary: str, category: str, priority: str = "MEDIUM") -> Ticket:
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
            # Create a detached copy to return
            return Ticket(
                id=ticket.id,
                status=ticket.status,
                category=ticket.category,
                priority=ticket.priority,
                summary=ticket.summary,
                created_at=ticket.created_at,
                updated_at=ticket.updated_at
            )

    @staticmethod
    def get_ticket(ticket_id: str) -> Optional[Ticket]:
        with SessionLocal() as db:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not ticket:
                return None
            # Return detached copy
            return Ticket(
                id=ticket.id,
                status=ticket.status,
                category=ticket.category,
                priority=ticket.priority,
                summary=ticket.summary,
                created_at=ticket.created_at,
                updated_at=ticket.updated_at
            )


class AuditLogRepository:
    
    @staticmethod
    def log_action(action: str, details: Dict[str, Any], session_id: Optional[str] = None) -> AuditLog:
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


class SessionRepository:
    @staticmethod
    def save_messages(session_id: str, messages_json: list[str]) -> None:
        """Save a list of serialized messages for a session."""
        from src.persistence.models import SessionMessage
        with SessionLocal() as db:
            for msg_json in messages_json:
                session_msg = SessionMessage(
                    session_id=session_id,
                    message_json=msg_json
                )
                db.add(session_msg)
            db.commit()

    @staticmethod
    def get_messages(session_id: str) -> list[str]:
        """Retrieve serialized messages for a session, ordered by creation time."""
        from src.persistence.models import SessionMessage
        with SessionLocal() as db:
            rows = db.query(SessionMessage).filter(SessionMessage.session_id == session_id).order_by(SessionMessage.created_at).all()
            return [row.message_json for row in rows]

