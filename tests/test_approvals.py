"""
tests/test_approvals.py
───────────────────────
Human-approval flow (spec §8/§11/§12):
  - ApprovalRepository lifecycle
  - request_approval / execute_approved_action guard behaviour
  - REST approval endpoints (human decision path)
"""
from __future__ import annotations

import os
import json
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")

from src.persistence.database import init_db
from src.persistence.repositories import ApprovalRepository, AuditLogRepository
from src.tools.approval import request_approval, execute_approved_action
from src.api.main import app


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def _request(session_id="s-approval-test", action="unlock_account", target="locked.user@company.com"):
    """Create a PENDING approval through the real tool surface; return the parsed dict."""
    from src.observability.request_context import set_request_context, clear_request_context
    set_request_context(session_id=session_id)
    try:
        payload = json.loads(request_approval(action=action, target=target, rationale="test rationale"))
    finally:
        clear_request_context()
    assert payload["status"] == "PENDING"
    return payload


# ── Repository lifecycle ───────────────────────────────────────────────────────

def test_request_creates_pending():
    req = _request()
    fetched = ApprovalRepository.get_approval(req["approval_id"])
    assert fetched is not None and fetched.id == req["approval_id"]
    assert fetched.status == "PENDING"


def test_decide_approve_then_execute_marks_executed():
    req = _request()
    decided = ApprovalRepository.decide(req["approval_id"], "APPROVED")
    assert decided.status == "APPROVED"
    assert ApprovalRepository.mark_executed(req["approval_id"]) is True
    final = ApprovalRepository.get_approval(req["approval_id"])
    assert final.status == "EXECUTED"


def test_double_decision_conflict():
    req = _request()
    assert ApprovalRepository.decide(req["approval_id"], "APPROVED") is not None
    # Second decision on non-pending record must be refused
    assert ApprovalRepository.decide(req["approval_id"], "REJECTED") is None


def test_invalid_decision_rejected():
    req = _request()
    with pytest.raises(ValueError):
        ApprovalRepository.decide(req["approval_id"], "MAYBE")


# ── Tool-level guards (enforcement outside the LLM) ──────────────────────────

def test_execution_blocked_when_pending():
    req = _request()
    result = json.loads(execute_approved_action("unlock_account", req["target"], req["approval_id"]))
    assert result["status"] == "PENDING"
    assert "result" not in result  # nothing was executed


def test_execution_denied_without_record():
    result = json.loads(execute_approved_action("unlock_account", "locked.user@company.com", "no-such-id"))
    assert result["status"] == "DENIED"


def test_audit_log_written_for_denial():
    before = _audit_count()
    execute_approved_action("unlock_account", "x@company.com", "bogus")
    assert _audit_count() >= before + 1


def test_execution_target_mismatch():
    req = _request()
    ApprovalRepository.decide(req["approval_id"], "APPROVED")
    result = json.loads(execute_approved_action("unlock_account", "someone.else@company.com", req["approval_id"]))
    assert result["status"] == "DENIED"


def test_full_happy_path_via_tools():
    req = _request()
    ApprovalRepository.decide(req["approval_id"], "APPROVED")
    result = json.loads(execute_approved_action("unlock_account", req["target"], req["approval_id"]))
    assert result["status"] == "success"
    assert "SUCCESS" in result["result"]
    assert ApprovalRepository.get_approval(req["approval_id"]).status == "EXECUTED"

    # Replay protection: second execution is refused
    replay = json.loads(execute_approved_action("unlock_account", req["target"], req["approval_id"]))
    assert replay["status"] == "ALREADY_EXECUTED"


def test_unknown_action_not_approvable():
    result = json.loads(request_approval(action="delete_database", target="prod"))
    assert result["status"] == "error"


def _audit_count() -> int:
    from src.persistence.database import SessionLocal
    from src.persistence.models import AuditLog
    with SessionLocal() as db:
        return db.query(AuditLog).count()


# ── REST endpoints ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_approvals_rest_flow():
    req = _request()
    approval_id = req["approval_id"]
    session = json.dumps(req)  # keep for clarity

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Listed as pending
        res = await client.get("/api/v1/approvals?status=PENDING")
        assert res.status_code == 200
        ids = [a["id"] for a in res.json()["approvals"]]
        assert approval_id in ids

        # Approve via REST
        res = await client.post(f"/api/v1/approvals/{approval_id}/approve")
        assert res.status_code == 200
        assert res.json()["status"] == "APPROVED"

        # Second decision conflicts
        res = await client.post(f"/api/v1/approvals/{approval_id}/reject")
        assert res.status_code == 409

        # Unknown id → 404
        res = await client.post(f"/api/v1/approvals/{uuid.uuid4()}/approve")
        assert res.status_code == 404
