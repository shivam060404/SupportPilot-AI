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
from src.agents.sqlite_history_provider import SQLiteHistoryProvider
from src.agents.escalation_agent import create_escalation_agent
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler, Message, AgentSession

log = get_logger(__name__)

# Initialize DB tables
init_db()

class TriageExecutor(Executor):
    @handler
    async def process(self, messages: list[Message], ctx: WorkflowContext) -> None:
        # Just pass the messages forward to be evaluated by the edge conditions
        await ctx.yield_output(messages)

def is_escalation_query(messages: list[Message]) -> bool:
    if not messages:
        return False
    # Check the last user message text
    try:
        content = messages[-1].text.lower()
    except Exception:
        content = str(messages[-1]).lower()
    return any(kw in content for kw in ["account", "password", "locked", "escalate", "manager", "ad", "unlock"])

def is_tier1_query(messages: list[Message]) -> bool:
    return not is_escalation_query(messages)

class SupportAgent:
    """
    Orchestrates the Tier 1 IT Support and Tier 2 Escalation Agents via MAF WorkflowBuilder.
    State is persisted to SQLite via SQLiteHistoryProvider.
    """

    def __init__(self) -> None:
        settings = get_settings()

        self._client = OpenAIChatClient(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )

        self._history_provider = SQLiteHistoryProvider()
        
        # ── Phase 2 Tools for IT Agent ──
        it_tools = [
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

        # ── Build Agents ──
        it_agent = af.create_harness_agent(
            client=self._client,
            id="supportpilot-it",
            name="Tier 1 Support",
            agent_instructions=SYSTEM_PROMPT,
            history_provider=self._history_provider,
            tools=it_tools,
            loop_max_iterations=10,
        )
        
        escalation_agent = create_escalation_agent(
            client=self._client,
            history_provider=self._history_provider,
        )
        
        triage = TriageExecutor(id="triage")

        # ── Build Workflow ──
        workflow = (
            WorkflowBuilder(start_executor=triage)
            .add_edge(triage, escalation_agent, condition=is_escalation_query)
            .add_edge(triage, it_agent, condition=is_tier1_query)
            .build()
        )
        
        # Convert workflow to an agent interface so we can call .run()
        self.workflow_agent = workflow.as_agent(name="SupportPilot")

    def _get_or_create_session(
        self, session_id: str
    ) -> tuple[af.Agent, af.AgentSession]:
        """
        Return the workflow agent and a session for the given session_id.
        History is automatically retrieved and saved to SQLite.
        """
        session = af.AgentSession(session_id=session_id)
        return self.workflow_agent, session

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
