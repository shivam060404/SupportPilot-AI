"""
core/audit/audit_logger.py
──────────────────────────
Structured audit logger for critical events.
"""
from typing import Optional, Dict, Any
from src.persistence.repositories import AuditLogRepository
from src.observability.logger import get_logger

log = get_logger(__name__)

class AuditLogger:
    @staticmethod
    def log_event(action: str, resource: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Logs a critical audit event to both the application logs and persistent storage.
        """
        log.info("audit_event", action=action, resource=resource, details=details)
        try:
            AuditLogRepository.log_event(action=action, resource=resource, details=details)
        except Exception as exc:
            log.error("audit_log_persistence_failed", error=str(exc))
