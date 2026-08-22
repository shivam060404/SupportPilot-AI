"""
src/agents/supervisor_agent.py
────────────────────────────────
Multi-agent IT support orchestration built on MAF WorkflowBuilder.

Architecture
────────────
                    ┌─ condition: escalation keywords ─▶ Tier-2 Escalation Agent
User ▶ TriageExecutor                                  │   tools: MCP AD lookups +
                    └─ condition: everything else ───▶ │            approval gate
                                                       ▼ Tier-1 Support Agent
                                                         tools: RAG search, service
                                                         status, ticket CRUD

Routing is a deterministic keyword pre-filter (fast, testable); the Tier-1
agent's system prompt performs the real per-issue classification. Sensitive
actions are gated by the DB-backed human approval flow in
src/tools/approval.py — enforcement lives outside the LLM.

Sessions are persisted to SQLite via SQLiteHistoryProvider, so conversations
survive restarts.
"""
from __future__ import annotations

import uuid
from typing import Optional

import agent_framework as af
from agent_framework_openai import OpenAIChatClient

from config import get_settings
from src.agents.prompts import SYSTEM_PROMPT
from src.observability.logger import get_logger
from src.observability.request_context import set_request_context
from src.persistence.database import init_db
from src.tools.search_knowledge_base import search_knowledge_base
from src.tools.check_service_status import check_service_status
from src.tools.create_ticket import create_ticket
from src.tools.get_ticket_status import get_ticket_status
from src.tools.approval import request_approval, execute_approved_action
from src.agents.sqlite_history_provider import SQLiteHistoryProvider
from src.agents.escalation_agent import create_escalation_agent

log = get_logger(__name__)

# Keywords whose presence in the latest user message routes to Tier 2.
# Deliberately narrow: bare "account"/"password" stay with Tier 1 (KB covers
# resets); lockouts, unlocks, managerial and AD matters escalate.
ESCALATION_KEYWORDS = (
    "locked",
    "lock out",
    "lockout",
    "unlock",
    "manager",
    "escalate",
    "escalation",
    "active directory",
    "ad account",
    "admin rights",
    "administrator access",
    "permissions request",
)


def is_escalation_query(messages: list) -> bool:
    """Deterministic pre-triage: does the latest message need Tier 2?"""
    if not messages:
        return False
    try:
        content = messages[-1].text.lower()
    except Exception:
        content = str(messages[-1]).lower()
    return any(kw in content for kw in ESCALATION_KEYWORDS)


def is_tier1_query(messages: list) -> bool:
    return not is_escalation_query(messages)


class TriageExecutor(af.Executor):
    @af.handler
    async def process(self, messages: list[af.Message], ctx: af.WorkflowContext) -> None:
        await ctx.yield_output(messages)


class SupportAgent:
    """
    Orchestrates the Tier 1 IT Support and Tier 2 Escalation Agents via a MAF
    workflow. State is persisted to SQLite via SQLiteHistoryProvider.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # Ensure schema exists (moved out of module import time).
        init_db()

        self.llm_ready = bool(settings.groq_api_key)
        self._client = None
        self.workflow_agent = None
        self._history_provider = SQLiteHistoryProvider()

        if not self.llm_ready:
            # Degrade gracefully: REST endpoints (tickets/approvals/services/
            # sessions) keep working; chat returns a clear configuration error.
            log.error("support_agent_init_no_api_key")
            return

        self._client = OpenAIChatClient(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url=settings.groq_base_url,
        )

        it_tools = [
            search_knowledge_base,
            check_service_status,
            create_ticket,
            get_ticket_status,
        ]

        log.info(
            "support_agent_init",
            model=settings.groq_model,
            base_url=settings.groq_base_url,
        )

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

        workflow = (
            af.WorkflowBuilder(start_executor=triage)
            .add_edge(triage, escalation_agent, condition=is_escalation_query)
            .add_edge(triage, it_agent, condition=is_tier1_query)
            .build()
        )

        self.workflow_agent = workflow.as_agent(name="SupportPilot")

    def _get_or_create_session(self, session_id: str) -> tuple[af.Agent, af.AgentSession]:
        session = af.AgentSession(session_id=session_id)
        return self.workflow_agent, session

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        Send a user message to the MAF workflow and return a structured result.

        Returns dict with keys: session_id, response, trace_id.
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        trace_id = trace_id or str(uuid.uuid4())

        # Deterministic code (tools/guards) reads identity from here —
        # never from LLM-supplied values.
        set_request_context(session_id=session_id, trace_id=trace_id)

        if not self.llm_ready or self.workflow_agent is None:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. Set it in .env and restart the server."
            )

        log.info(
            "chat_request",
            session_id=session_id,
            trace_id=trace_id,
            message_length=len(message),
        )

        agent, session = self._get_or_create_session(session_id)

        try:
            response: af.AgentResponse = await agent.run(
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
