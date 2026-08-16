"""
src/agents/supervisor_agent.py
────────────────────────────────
Phase 1 — Single MAF agent backed by Groq LLaMA via the OpenAI-compatible
endpoint.

Architecture
────────────
  OpenAIChatClient(base_url=groq)
       ↓
  create_harness_agent(...)   ← MAF batteries-included agent
       ↓
  agent.run(messages, session=session)
       ↓
  AgentResponse.text

Session management
──────────────────
Each user conversation is keyed by a session_id. We use MAF's built-in
InMemoryHistoryProvider so the agent automatically maintains multi-turn
context per session.  Phase 3 will swap this for a persistent store.

Usage (internal)
──────────────────
    from src.agents.supervisor_agent import SupportAgent
    agent = SupportAgent()          # singleton-friendly
    response = await agent.chat("My VPN is broken", session_id="user-123")
"""
from __future__ import annotations

import uuid
from typing import Optional

import agent_framework as af
from agent_framework_openai import OpenAIChatClient

from config import get_settings
from src.agents.prompts import SYSTEM_PROMPT
from src.observability.logger import get_logger
from src.persistence.database import init_db
from src.tools.search_knowledge_base import search_knowledge_base
from src.tools.check_service_status import check_service_status
from src.tools.create_ticket import create_ticket
from src.tools.get_ticket_status import get_ticket_status

log = get_logger(__name__)

# Initialize DB tables
init_db()

class SupportAgent:
    """
    Wraps a MAF harness agent with Groq LLaMA and manages per-session
    history using InMemoryHistoryProvider instances.

    Thread-safety: each session gets its own InMemoryHistoryProvider,
    so concurrent requests to different sessions are isolated.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # ── MAF Chat Client pointing at Groq's OpenAI-compatible endpoint ────
        self._client = OpenAIChatClient(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )

        # ── Session → HistoryProvider map (Phase 3 will persist to disk/DB) ──
        self._history_providers: dict[str, af.InMemoryHistoryProvider] = {}
        
        # ── Phase 2 Tools ──
        self._tools = [
            search_knowledge_base,
            check_service_status,
            create_ticket,
            get_ticket_status
        ]

        log.info(
            "support_agent_init",
            model=settings.groq_model,
            base_url=settings.groq_base_url,
        )

    def _get_or_create_session(
        self, session_id: str
    ) -> tuple[af.Agent, af.AgentSession]:
        """
        Return (agent, session) for the given session_id.
        A fresh InMemoryHistoryProvider is created once per session_id.
        """
        if session_id not in self._history_providers:
            self._history_providers[session_id] = af.InMemoryHistoryProvider()
            log.debug("session_created", session_id=session_id)

        history_provider = self._history_providers[session_id]

        agent = af.create_harness_agent(
            client=self._client,
            id="supportpilot-supervisor",
            name="SupportPilot",
            agent_instructions=SYSTEM_PROMPT,
            history_provider=history_provider,
            # Phase 2: Add tools
            tools=self._tools,
            # Guard against runaway loops
            loop_max_iterations=10,
        )

        # MAF AgentSession ties the run to the history provider's stored thread
        session = af.AgentSession(session_id=session_id)
        return agent, session

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> dict:
        """
        Send a user message to the MAF agent and return a structured result.

        Parameters
        ----------
        message:    The user's raw input string.
        session_id: Conversation identifier. Auto-generated if None.

        Returns
        -------
        dict with keys:
            session_id  — the session used
            response    — agent's text reply
            trace_id    — correlation ID for this invocation
        """
        if not session_id:
            session_id = str(uuid.uuid4())

        trace_id = str(uuid.uuid4())
        log.info(
            "chat_request",
            session_id=session_id,
            trace_id=trace_id,
            message_length=len(message),
        )

        agent, session = self._get_or_create_session(session_id)

        try:
            response: af.AgentResponse = await agent.run(  # type: ignore[assignment]
                messages=message,
                session=session,
            )

            reply_text: str = response.text or "(no response)"

            log.info(
                "chat_response",
                session_id=session_id,
                trace_id=trace_id,
                response_length=len(reply_text),
            )

            return {
                "session_id": session_id,
                "response": reply_text,
                "trace_id": trace_id,
            }

        except Exception as exc:
            log.error(
                "chat_error",
                session_id=session_id,
                trace_id=trace_id,
                error=str(exc),
                exc_info=True,
            )
            raise
