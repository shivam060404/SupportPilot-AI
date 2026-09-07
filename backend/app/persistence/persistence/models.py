"""
src/persistence/models.py
─────────────────────────
SQLAlchemy ORM models.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Text, DateTime, JSON
from src.persistence.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    status = Column(String, default="OPEN", index=True)
    category = Column(String, index=True)
    priority = Column(String, default="MEDIUM")
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    session_id = Column(String, index=True, nullable=True)
    action = Column(String, index=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class SessionMessage(Base):
    __tablename__ = "session_messages"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    session_id = Column(String, index=True, nullable=False)
    message_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class ApprovalRequest(Base):
    """A human-in-the-loop approval gate for sensitive/privileged actions.

    Lifecycle: PENDING -> APPROVED | REJECTED -> EXECUTED (if approved action ran)
    The execution-side guard refuses to run a sensitive action unless a matching
    APPROVED record exists — enforcement lives outside the LLM.
    """

    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    session_id = Column(String, index=True, nullable=False)
    action = Column(String, index=True, nullable=False)       # e.g. unlock_account
    target = Column(String, nullable=False)                    # e.g. user email
    rationale = Column(Text, nullable=True)
    status = Column(String, default="PENDING", index=True)     # PENDING/APPROVED/REJECTED/EXECUTED
    requested_at = Column(DateTime(timezone=True), default=utc_now)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
