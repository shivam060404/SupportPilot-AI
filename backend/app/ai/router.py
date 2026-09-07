"""
core/orchestration/router.py
─────────────────────────────
Routing logic to direct chat requests to either Tier-1 Support or Tier-2 Escalation.

Extracts the triage logic from the old supervisor_agent.py.
"""
from __future__ import annotations

from typing import Optional

from src.observability.logger import get_logger

log = get_logger(__name__)

# Keywords whose presence in the latest user message routes to Tier 2.
ESCALATION_KEYWORDS = {
    "locked",
    "lock out",
    "lockout",
    "unlock",
    "manager",
    "escalate",
    "escalation",
    "active directory",
    "ad account",
    "admin rights",
    "administrator access",
    "permissions request",
}


def _latest_text(payload: object) -> str:
    """Extract the latest user text from whatever travels along the edge."""
    # Handle agent_framework AgentExecutorRequest or raw list of messages
    messages = getattr(payload, "messages", payload)
    try:
        return (messages[-1].text or "").lower()
    except Exception:
        return str(messages).lower()


def _has_open_approval_loop(session_id: Optional[str]) -> bool:
    """Sticky-routing signal: an unresolved approval keeps the chat in Tier 2."""
    if not session_id:
        return False
    try:
        from src.persistence.repositories import ApprovalRepository
        return any(
            r.status in {"PENDING", "APPROVED"}
            for r in ApprovalRepository.list_approvals(session_id=session_id, limit=10)
        )
    except Exception:
        return False


def is_escalation_query(payload: object) -> bool:
    """Deterministic pre-triage: does the latest exchange need Tier 2?

    Escalates when the latest message matches sensitive keywords OR when the
    session has an unresolved human-approval loop.
    """
    if not payload:
        return False

    latest = _latest_text(payload)
    if any(kw in latest for kw in ESCALATION_KEYWORDS):
        return True

    try:
        from src.observability.request_context import get_session_id
        return _has_open_approval_loop(get_session_id())
    except Exception:
        return False


def is_tier1_query(payload: object) -> bool:
    """Tier 1 if not an escalation query."""
    return not is_escalation_query(payload)
