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
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.schemas import ChatRequest, ChatResponse, HealthResponse, ErrorResponse
from src.observability.logger import get_logger, bind_trace_context, clear_trace_context
from src.observability.request_context import set_request_context, clear_request_context
from src.observability.tooltrace import start_tool_trace, stop_tool_trace, start_artifacts, collect_artifacts
from core.guardrails.pipeline import GuardrailPipeline
from config import get_settings

log = get_logger(__name__)
router = APIRouter()

# Global pipeline instance (stateless)
_guardrail_pipeline = GuardrailPipeline()


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
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    session_id = body.session_id or str(uuid.uuid4())
    bind_trace_context(trace_id=trace_id, session_id=session_id)
    set_request_context(trace_id=trace_id, session_id=session_id)

    from core.orchestration.agents.tier1_agent import SupportAgent
    agent: SupportAgent = request.app.state.agent

    message = body.message
    if body.category:
        message = f"[Employee selected category: {body.category}]\n{message}"

    try:
        start_tool_trace()
        start_artifacts()

        # The agent execution wrapper to pass to the pipeline
        async def run_agent(msg: str) -> Dict[str, Any]:
            return await agent.chat(
                message=msg,
                session_id=session_id,
            )

        # Run through the guardrail pipeline
        pipeline_result, agent_result = await _guardrail_pipeline.run(
            message=message,
            agent_fn=run_agent,
            context={"category": body.category},
            session_id=session_id,
        )

        artifacts = collect_artifacts()
        tool_trace = stop_tool_trace()

        # Handle early block by input guardrails
        if pipeline_result.blocked:
            return ChatResponse(
                session_id=session_id,
                response=pipeline_result.user_block_message or "Request blocked.",
                trace_id=trace_id,
                tool_trace=tool_trace,
                sources=[],
                blocked=True,
                block_reason=pipeline_result.block_reason,
                pii_detected=pipeline_result.pii_detected,
                grounding=pipeline_result.grounding_metadata,
            )

        # Agent ran successfully, we have an agent_result
        if agent_result is None:
            # Fallback just in case pipeline allowed but agent_result is None
            raise RuntimeError("Pipeline passed but returned None agent_result")

        # The pipeline replaces agent_result["response"] if needed
        # and artifacts might have been modified. 
        # But we pull rag sources from agent_result if there
        rag_sources = agent_result.get("rag_sources", []) or artifacts.get("sources", [])

        return ChatResponse(
            session_id=session_id,
            response=agent_result.get("response", ""),
            trace_id=trace_id,
            tool_trace=agent_result.get("tool_trace") or tool_trace,
            sources=rag_sources,
            blocked=False,
            block_reason=None,
            pii_detected=pipeline_result.pii_detected,
            grounding=pipeline_result.grounding_metadata,
        )

    except Exception as exc:
        stop_tool_trace()
        collect_artifacts()
        log.error("chat_endpoint_error", error=str(exc), trace_id=trace_id, exc_info=True)
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
