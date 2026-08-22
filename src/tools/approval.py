"""
src/tools/approval.py
─────────────────────
Human-in-the-loop approval tools (spec §8 `request_approval`, §11/§12).

Design — enforcement lives OUTSIDE the LLM:
  1. `request_approval` persists a PENDING ApprovalRequest row and tells the
     agent to stop and wait for the human decision.
  2. A human (employee in the UI, or IT staff) approves/rejects via REST
     endpoints — the LLM cannot approve its own request.
  3. `execute_approved_action` is the ONLY way a sensitive action runs. It
     verifies in the database that a matching APPROVED record exists before
     touching the business service, then marks the record EXECUTED.
     Every decision point is audit-logged.
"""
import json

import agent_framework as af

from src.observability.logger import get_logger
from src.observability.request_context import get_session_id
from src.observability.tooltrace import traced_tool
from src.persistence.repositories import ApprovalRepository, AuditLogRepository
from src.services import ad_directory

log = get_logger(__name__)

# Actions considered privileged — each requires a human approval record.
SENSITIVE_ACTIONS = {
    "unlock_account": ad_directory.unlock_account,
}


@af.tool(name="request_approval", description=(
    "Request human approval for a sensitive/privileged action (e.g. unlock_account). "
    "Call this BEFORE performing the action, then STOP and tell the user an approval is "
    "pending. Do NOT attempt the action until approval is granted."
))
@traced_tool("request_approval")
def request_approval(action: str, target: str, rationale: str = "") -> str:
    """
    Create a human approval request for a sensitive action.

    Args:
        action: The sensitive action name, e.g. 'unlock_account'.
        target: What the action applies to, e.g. the employee's email.
        rationale: Why the action is needed.
    """
    session_id = get_session_id() or "unknown"

    action = (action or "").strip()
    target = (target or "").strip()

    if action not in SENSITIVE_ACTIONS:
        AuditLogRepository.log_action(
            action="security_blocked_approval_request",
            details={"reason": "unknown_action", "requested_action": action, "target": target},
            session_id=session_id,
        )
        return json.dumps({
            "status": "error",
            "message": f"Action '{action}' is not a recognized approvable action. "
                       f"Approvable actions: {sorted(SENSITIVE_ACTIONS)}.",
        })

    req = ApprovalRepository.request_approval(
        session_id=session_id, action=action, target=target, rationale=rationale
    )
    log.info(
        "approval_requested",
        approval_id=req.id,
        approval_action=action,
        target=target,
        session_id=session_id,
    )
    return json.dumps({
        "status": "PENDING",
        "approval_id": req.id,
        "action": action,
        "target": target,
        "message": (
            f"Approval {req.id} is PENDING. STOP NOW. Tell the user that approval is required "
            "and they (or IT staff) can approve or reject it in the SupportPilot UI. "
            "Wait for the user's next message; do not call execute_approved_action yet."
        ),
    })


@af.tool(name="execute_approved_action", description=(
    "Execute a sensitive action ONLY after human approval was granted in the UI. "
    "Requires the approval ID. The system independently verifies the approval record; "
    "unapproved executions are blocked and audited."
))
@traced_tool("execute_approved_action")
def execute_approved_action(action: str, target: str, approval_id: str) -> str:
    """
    Execute a sensitive action after verifying its human approval record.

    Args:
        action: The sensitive action name, e.g. 'unlock_account'.
        target: What the action applies to (must match the approval record).
        approval_id: ID of the approval granted by the human.
    """
    session_id = get_session_id() or "unknown"
    action = (action or "").strip()
    target = (target or "").strip()
    approval_id = (approval_id or "").strip()

    def _deny(reason: str, detail: dict) -> str:
        AuditLogRepository.log_action(
            action="security_blocked_sensitive_execution",
            details={"reason": reason, **detail},
            session_id=session_id,
        )
        log.warning("sensitive_execution_blocked", reason=reason, **detail)
        return json.dumps({
            "status": "DENIED",
            "message": f"Execution denied: {reason}. The action was NOT performed.",
        })

    handler = SENSITIVE_ACTIONS.get(action)
    if handler is None:
        return _deny("unknown_action", {"requested_action": action, "target": target})

    record = ApprovalRepository.get_approval(approval_id) if approval_id else None
    if record is None:
        return _deny("approval_not_found", {"action": action, "target": target, "approval_id": approval_id})

    if record.action != action or record.target != target:
        return _deny("approval_target_mismatch", {
            "action": action, "target": target,
            "approval_action": record.action, "approval_target": record.target,
        })

    if record.status == "PENDING":
        return json.dumps({
            "status": "PENDING",
            "message": "Approval has not been decided yet. Ask the user to approve it in the UI.",
            "approval_id": approval_id,
        })
    if record.status == "REJECTED":
        return json.dumps({
            "status": "REJECTED",
            "message": "The human rejected this request. Do not retry. Offer alternatives or escalate.",
            "approval_id": approval_id,
        })
    if record.status == "EXECUTED":
        return json.dumps({
            "status": "ALREADY_EXECUTED",
            "message": "This approval was already executed. Do not execute again.",
            "approval_id": approval_id,
        })
    if record.status != "APPROVED":
        return _deny("invalid_approval_state", {"state": record.status, "approval_id": approval_id})

    # ── Guard passed: run the deterministic business service ──
    result = handler(target)
    ApprovalRepository.mark_executed(approval_id)
    AuditLogRepository.log_action(
        action="sensitive_action_executed",
        details={"approval_id": approval_id, "action": action, "target": target, "result": result},
        session_id=session_id,
    )
    log.info("sensitive_action_executed", approval_id=approval_id, action=action, session_id=session_id)
    return json.dumps({
        "status": "success",
        "approval_id": approval_id,
        "result": result,
    })
