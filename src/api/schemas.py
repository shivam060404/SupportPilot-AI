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
    category: Optional[str] = Field(
        default=None,
        description="Optional category hint from the UI (VPN, Password, WiFi, ...). Used as a routing hint only.",
        examples=["VPN"],
    )


class ToolTraceItem(BaseModel):
    """One tool invocation observed during the agent run (spec §14)."""
    tool: str
    phase: str
    args: Optional[dict] = None
    duration_ms: Optional[float] = None
    ok: Optional[bool] = None
    error: Optional[str] = None


class SourceItem(BaseModel):
    """A retrieved knowledge-base source cited for grounding."""
    title: str
    category: Optional[str] = None
    file: Optional[str] = None
    score: Optional[float] = None


class ChatResponse(BaseModel):
    """Agent's reply to the employee."""
    session_id: str = Field(description="Session ID to use in follow-up requests.")
    response: str = Field(description="Agent's answer / troubleshooting steps.")
    trace_id: str = Field(description="Correlation ID for this request (for logs).")
    phase: str = Field(default="Phase 6", description="Current system phase.")
    tool_trace: list[ToolTraceItem] = Field(
        default_factory=list,
        description="Ordered log of tools the agent invoked while producing this reply.",
    )
    sources: list[SourceItem] = Field(
        default_factory=list,
        description="Knowledge-base chunks used to ground the answer.",
    )


# ── /health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""

    status: str = Field(default="ok")
    app_name: str
    env: str
    phase: str = Field(default="Phase 6 — Tests/Observability/Docker")


# ── /tickets ─────────────────────────────────────────────────────────────────

class TicketResponse(BaseModel):
    id: str
    status: str
    category: str
    priority: str
    summary: str
    created_at: str
    updated_at: str

# ── /sessions ────────────────────────────────────────────────────────────────

class MessageHistoryItem(BaseModel):
    role: str
    content: str
    
class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageHistoryItem]

# ── /services ────────────────────────────────────────────────────────────────

class ServiceStatusItem(BaseModel):
    service: str
    status: str
    message: str

class ServicesStatusResponse(BaseModel):
    services: list[ServiceStatusItem]

# ── /approvals ───────────────────────────────────────────────────────────────

class ApprovalItem(BaseModel):
    id: str
    session_id: str
    action: str
    target: str
    rationale: Optional[str] = None
    status: str
    requested_at: Optional[str] = None
    decided_at: Optional[str] = None
    executed_at: Optional[str] = None


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalItem]


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$", description="Human decision.")


# ── Tickets (write/list) ─────────────────────────────────────────────────────

class TicketCreateRequest(BaseModel):
    summary: str = Field(..., min_length=3, max_length=2000)
    category: str = Field(..., min_length=1, max_length=64)
    priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")


# ── Error ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    trace_id: Optional[str] = None
