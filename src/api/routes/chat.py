"""
src/api/routes/chat.py
──────────────────────
POST /chat    — main conversation endpoint
GET  /health  — liveness probe

The route opens a tool-trace scope around the agent run and returns what the
agent actually did (tool calls, RAG sources) alongside the reply — making each
interaction explainable (spec §14).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.schemas import ChatRequest, ChatResponse, HealthResponse, ErrorResponse
from src.observability.logger import get_logger, bind_trace_context, clear_trace_context
from src.observability.request_context import set_request_context, clear_request_context
from src.observability.tooltrace import start_tool_trace, stop_tool_trace, start_artifacts, collect_artifacts
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
    Send a natural-language IT issue to the SupportPilot agent.

    - Include `session_id` from a previous response to continue a conversation.
    - Omit `session_id` to start a fresh session.
    - Optional `category` hints the pre-triage router.
    """
    # Reuse the middleware-generated trace ID so header, logs and response match.
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    session_id = body.session_id or "new"
    bind_trace_context(trace_id=trace_id, session_id=session_id)
    set_request_context(trace_id=trace_id)

    # Lazy-import avoids circular deps and allows the app to start without a key
    from src.agents.supervisor_agent import SupportAgent
    agent: SupportAgent = request.app.state.agent

    message = body.message
    if body.category:
        # Deterministic hint prepended for routing/metadata — never trusted alone.
        message = f"[Employee selected category: {body.category}]\n{message}"

    try:
        set_request_context(session_id=body.session_id)  # tools read this
        start_tool_trace()
        start_artifacts()

        result = await agent.chat(
            message=message,
            session_id=body.session_id,
            trace_id=trace_id,
        )

        artifacts = collect_artifacts()
        return ChatResponse(
            session_id=result["session_id"],
            response=result["response"],
            trace_id=result["trace_id"],
            tool_trace=result.get("tool_trace") or stop_tool_trace(),
            sources=artifacts.get("sources", []),
        )
    except Exception as exc:
        stop_tool_trace()
        collect_artifacts()
        log.error("chat_endpoint_error", error=str(exc), trace_id=trace_id)
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {exc}",
        )
    finally:
        clear_trace_context()
        clear_request_context()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        app_name=settings.app_name,
        env=settings.app_env
    )
