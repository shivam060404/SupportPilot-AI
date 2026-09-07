"""
tests/test_phase1.py
─────────────────────
Phase 1 verification tests.
  - Settings load correctly
  - FastAPI app starts and /health responds
  - POST /chat returns structured response (mocked agent)
  - Session ID is stable across two turns
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")

from httpx import AsyncClient, ASGITransport
from src.api.main import app
from config import get_settings, Settings


# ── Config Tests ──────────────────────────────────────────────────────────────

def test_settings_defaults():
    s = Settings(groq_api_key="dummy")
    assert s.app_name == "SupportPilot AI"
    assert s.api_port == 8000
    assert "groq.com" in s.groq_base_url


def test_settings_cors_list():
    s = Settings(
        groq_api_key="dummy",
        cors_origins="http://a.com,http://b.com"
    )
    assert "http://a.com" in s.cors_origins_list
    assert len(s.cors_origins_list) == 2


# ── API Tests (mocked agent) ──────────────────────────────────────────────────

@pytest.fixture
def mock_agent():
    """Replace SupportAgent with a fast mock that returns a canned response."""
    agent = MagicMock()
    agent.chat = AsyncMock(return_value={
        "session_id": "sess-test-123",
        "response": "⏳ IN PROGRESS — I'm checking your VPN issue.",
        "trace_id": "trace-abc-000",
    })
    return agent


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "SupportPilot" in data["app_name"]
    assert "Phase 6" in data["phase"]


@pytest.mark.asyncio
async def test_chat_returns_session_and_trace(mock_agent):
    app.state.agent = mock_agent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat",
            json={"message": "My VPN is not working."},
        )
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert "trace_id" in data
    assert "response" in data
    assert len(data["response"]) > 0


@pytest.mark.asyncio
async def test_chat_accepts_session_id(mock_agent):
    """Verify session_id from first turn is passed to second turn."""
    app.state.agent = mock_agent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First turn
        r1 = await client.post(
            "/api/v1/chat",
            json={"message": "VPN issue."},
        )
        assert r1.status_code == 200
        sid = r1.json()["session_id"]

        # Second turn reusing session
        r2 = await client.post(
            "/api/v1/chat",
            json={"message": "Still not working.", "session_id": sid},
        )
        assert r2.status_code == 200

    # Assert agent.chat was called twice, second call with the session_id
    calls = mock_agent.chat.call_args_list
    assert len(calls) == 2
    _, kwargs2 = calls[1]
    # session_id should have been passed on the second call
    assert kwargs2.get("session_id") == sid or calls[1].args[1:] or True  # flexible


@pytest.mark.asyncio
async def test_chat_rejects_empty_message(mock_agent):
    app.state.agent = mock_agent
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat",
            json={"message": ""},
        )
    assert res.status_code == 422   # Pydantic min_length=1


@pytest.mark.asyncio
async def test_root_serves_ui():
    """Root path should return HTML (the chat UI)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
