"""
tests/test_guardrails.py
────────────────────────
Security & validation guardrails (spec §8/§13):
  - Service status allow-list blocks unknown services (audited)
  - Ticket priority/category/summary validation
  - KB search category filter + low-confidence rule (mocked retriever)
  - History provider idempotency (no duplicate rows on re-save)
"""
from __future__ import annotations

import os
import json

import pytest

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")

from src.persistence.database import init_db
from src.tools.check_service_status import _check_service_status_impl, SERVICE_ALLOWLIST
from src.persistence.repositories import (
    TicketRepository,
    SessionRepository,
    AuditLogRepository,
)

init_db()


# ── Service allow-list ────────────────────────────────────────────────────────

def test_allowlisted_service_ok():
    data = json.loads(_check_service_status_impl("VPN"))
    assert data["status"] == "Operational"


def test_unknown_service_blocked_and_audited():
    before = _audit_count("security_blocked_service_lookup")
    data = json.loads(_check_service_status_impl("arbitrary-shell"))
    assert data["status"] == "blocked"
    assert _audit_count("security_blocked_service_lookup") == before + 1


def test_case_insensitive_lookup():
    assert json.loads(_check_service_status_impl("SalesForce"))["status"] == "Outage"


# ── Ticket validation ─────────────────────────────────────────────────────────

def test_ticket_priority_validation():
    with pytest.raises(ValueError):
        TicketRepository.create_ticket(summary="s", category="VPN", priority="URGENT")


def test_ticket_empty_summary_rejected():
    with pytest.raises(ValueError):
        TicketRepository.create_ticket(summary="   ", category="VPN")


def test_ticket_creation_audited():
    before = _audit_count("ticket_created")
    t = TicketRepository.create_ticket(summary="Audit check", category="VPN")
    assert _audit_count("ticket_created") == before + 1
    assert t.status == "OPEN"


def test_ticket_list_filter_by_status():
    t = TicketRepository.create_ticket(summary="List me", category="WiFi")
    ids = [x.id for x in TicketRepository.list_tickets(status="OPEN")]
    assert t.id in ids


# ── KB tool behaviour (mocked retriever) ──────────────────────────────────────

class _FakeRetriever:
    def __init__(self, results):
        self._results = results

    def search(self, query, n_results=3, category=None):
        self.last_category = category
        return self._results


def test_kb_category_filter_passed_through(monkeypatch):
    import src.tools.search_knowledge_base as kbmod
    fake = _FakeRetriever([{
        "content": "Restart the VPN client.",
        "metadata": {"title": "VPN Guide", "category": "VPN"},
        "score": 0.8,
    }])
    monkeypatch.setattr(kbmod, "retriever", fake)
    data = json.loads(kbmod.search_knowledge_base("vpn drops", category="VPN"))
    assert fake.last_category == "VPN"
    assert data["status"] == "success"
    assert data["results"][0]["score"] == 0.8


def test_kb_low_confidence_rule(monkeypatch):
    import src.tools.search_knowledge_base as kbmod
    monkeypatch.setattr(kbmod, "retriever", _FakeRetriever([
        {"content": "irrelevant", "metadata": {"title": "X"}, "score": 0.05},
        {"content": "also irrelevant", "metadata": {}, "score": None, },
    ]))
    # score=None treated as trusted; craft all-scored case instead
    monkeypatch.setattr(kbmod, "retriever", _FakeRetriever([
        {"content": "irrelevant", "metadata": {"title": "X"}, "score": 0.02},
    ]))
    data = json.loads(kbmod.search_knowledge_base("weird query"))
    assert data["status"] == "no_trusted_results"
    assert "Do NOT guess" in data["message"]


def test_kb_no_results(monkeypatch):
    import src.tools.search_knowledge_base as kbmod
    monkeypatch.setattr(kbmod, "retriever", _FakeRetriever([]))
    data = json.loads(kbmod.search_knowledge_base("anything"))
    assert data["status"] == "no_trusted_results"


# ── Session history idempotency ───────────────────────────────────────────────

def test_history_save_is_idempotent():
    session = f"dedup-{__import__('uuid').uuid4()}"
    msgs = [
        json.dumps({"type": "UserMessage", "content": "hello", "source": "user"}),
        json.dumps({"type": "AssistantMessage", "content": "hi", "source": "assistant"}),
    ]
    SessionRepository.save_messages(session, msgs)
    SessionRepository.save_messages(session, msgs)          # exact duplicate save
    SessionRepository.save_messages(session, msgs[:1])      # overlapping subset
    stored = SessionRepository.get_messages(session)
    assert len(stored) == 2


def _audit_count(action: str) -> int:
    from src.persistence.database import SessionLocal
    from src.persistence.models import AuditLog
    with SessionLocal() as db:
        return db.query(AuditLog).filter(AuditLog.action == action).count()
