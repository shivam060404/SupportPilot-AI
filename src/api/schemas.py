"""
src/api/schemas.py
────────────────────
Pydantic v2 request / response models for the SupportPilot API.
All public API shapes are defined here — never inline in route handlers.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── /chat ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming employee chat message."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="The employee's IT issue description.",
        examples=["My VPN keeps disconnecting every 10 minutes."],
    )
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation session ID. Omit to start a new session. "
            "Include on follow-up messages to maintain context."
        ),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class ChatResponse(BaseModel):
    """Agent's reply to the employee."""
    session_id: str = Field(description="Session ID to use in follow-up requests.")
    response: str = Field(description="Agent's answer / troubleshooting steps.")
    trace_id: str = Field(description="Correlation ID for this request (for logs).")
    phase: str = Field(default="Phase 1", description="Current system phase.")


# ── /health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    app_name: str
    version: str = Field(default="1.0.0-phase1")
    phase: str = Field(default="Phase 1 — Single Agent + LLM")


# ── Error ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    trace_id: Optional[str] = None
