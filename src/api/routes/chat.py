"""
src/api/routes/chat.py
──────────────────────
POST /chat    — main conversation endpoint
GET  /health  — liveness probe
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.schemas import ChatRequest, ChatResponse, HealthResponse, ErrorResponse
from src.observability.logger import get_logger, bind_trace_context, clear_trace_context
from config import get_settings

log = get_logger(__name__)
router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Send an IT support message to the SupportPilot agent",
    tags=["Chat"],
)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Send a natural-language IT issue to the SupportPilot MAF agent.

    - Include `session_id` from a previous response to continue a conversation.
    - Omit `session_id` to start a fresh session.
    """
    trace_id = str(uuid.uuid4())
    bind_trace_context(trace_id=trace_id, session_id=body.session_id or "new")

    # Lazy-import avoids circular deps and allows the app to start without a key
    from src.agents.supervisor_agent import SupportAgent
    agent: SupportAgent = request.app.state.agent

    try:
        result = await agent.chat(
            message=body.message,
            session_id=body.session_id,
        )
        return ChatResponse(
            session_id=result["session_id"],
            response=result["response"],
            trace_id=result["trace_id"],
        )
    except Exception as exc:
        log.error("chat_endpoint_error", error=str(exc), trace_id=trace_id)
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {exc}",
        )
    finally:
        clear_trace_context()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(app_name=settings.app_name)
