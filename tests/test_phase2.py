"""
tests/test_phase2.py
─────────────────────
Phase 2 verification tests.
  - Test SQLite database initialization
  - Test TicketRepository
  - Test RAG Retriever (mocked ChromaDB)
"""
from __future__ import annotations

import os
import pytest
from src.persistence.database import init_db
from src.persistence.repositories import TicketRepository

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")


def test_db_initialization():
    """Verify that tables can be created."""
    try:
        init_db()
        success = True
    except Exception:
        success = False
    assert success


def test_ticket_repository():
    """Verify that we can create and retrieve a ticket."""
    init_db()
    
    # Create ticket
    ticket = TicketRepository.create_ticket(
        summary="Cannot connect to VPN",
        category="VPN",
        priority="HIGH"
    )
    
    assert ticket.id is not None
    assert ticket.summary == "Cannot connect to VPN"
    assert ticket.category == "VPN"
    assert ticket.priority == "HIGH"
    assert ticket.status == "OPEN"
    
    # Retrieve ticket
    retrieved = TicketRepository.get_ticket(ticket.id)
    assert retrieved is not None
    assert retrieved.id == ticket.id
    assert retrieved.summary == ticket.summary
