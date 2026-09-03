"""
core/privacy/retention.py
──────────────────────────
Data retention policies for session data and audit logs.

Retention defaults (configurable via environment):
  - Session messages: 90 days
  - Audit logs: 365 days (compliance)
  - Approval records: 365 days
  - Ticket data: 730 days (2 years)

Usage:
    from core.privacy.retention import RetentionManager
    manager = RetentionManager()
    deleted = manager.purge_expired()
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Dict

from src.observability.logger import get_logger

log = get_logger(__name__)


@dataclass
class RetentionPolicy:
    """Defines data retention for a table/entity."""
    entity: str
    retention_days: int
    description: str


DEFAULT_POLICIES = [
    RetentionPolicy("session_messages", int(os.getenv("RETENTION_SESSIONS_DAYS", "90")),
                    "Chat session conversation history"),
    RetentionPolicy("audit_logs", int(os.getenv("RETENTION_AUDIT_DAYS", "365")),
                    "Security and action audit trail"),
    RetentionPolicy("approval_requests", int(os.getenv("RETENTION_APPROVALS_DAYS", "365")),
                    "Human-in-the-loop approval records"),
    RetentionPolicy("tickets", int(os.getenv("RETENTION_TICKETS_DAYS", "730")),
                    "IT support ticket history"),
]


class RetentionManager:
    """
    Enforces data retention policies by purging expired records.

    Call `purge_expired()` on a schedule (e.g., nightly cron) or at startup.
    All deletions are logged to the audit trail.
    """

    def __init__(self, policies: list[RetentionPolicy] | None = None) -> None:
        self.policies = policies or DEFAULT_POLICIES

    def purge_expired(self) -> Dict[str, int]:
        """
        Delete records older than their retention period.
        Returns a dict of {entity: rows_deleted}.
        """
        from src.persistence.database import SessionLocal
        from src.persistence.models import SessionMessage, AuditLog, ApprovalRequest, Ticket

        model_map = {
            "session_messages": (SessionMessage, SessionMessage.created_at),
            "audit_logs": (AuditLog, AuditLog.created_at),
            "approval_requests": (ApprovalRequest, ApprovalRequest.requested_at),
            "tickets": (Ticket, Ticket.created_at),
        }

        results: Dict[str, int] = {}
        now = datetime.now(timezone.utc)

        for policy in self.policies:
            model_info = model_map.get(policy.entity)
            if not model_info:
                continue
            model, date_col = model_info
            cutoff = now - timedelta(days=policy.retention_days)

            try:
                with SessionLocal() as db:
                    deleted = (
                        db.query(model)
                        .filter(date_col < cutoff)
                        .delete(synchronize_session=False)
                    )
                    db.commit()
                results[policy.entity] = deleted
                if deleted > 0:
                    log.info(
                        "retention_purge",
                        entity=policy.entity,
                        rows_deleted=deleted,
                        cutoff_date=cutoff.isoformat(),
                        retention_days=policy.retention_days,
                    )
            except Exception as exc:
                log.error("retention_purge_error", entity=policy.entity, error=str(exc))
                results[policy.entity] = -1

        return results

    def get_policy(self, entity: str) -> RetentionPolicy | None:
        return next((p for p in self.policies if p.entity == entity), None)
