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
from agent_framework_openai import OpenAIChatCompletionClient

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


def _latest_text(payload: object) -> str:
    """Extract the latest user text from whatever travels along the edge."""
    messages = getattr(payload, "messages", payload)  # AgentExecutorRequest | list
    try:
        return (messages[-1].text or "").lower()
    except Exception:
        return str(messages).lower()


def _has_open_approval_loop(session_id: Optional[str]) -> bool:
    """Sticky-routing signal: an unresolved approval keeps the chat in Tier 2."""
    if not session_id:
        return False
    try:
        from src.persistence.repositories import ApprovalRepository
        return any(
            r.status in {"PENDING", "APPROVED"}
            for r in ApprovalRepository.list_approvals(session_id=session_id, limit=10)
        )
    except Exception:
        return False


def is_escalation_query(payload: object) -> bool:
    """Deterministic pre-triage: does the latest exchange need Tier 2?

    Escalates when the latest message matches sensitive keywords OR when the
    session has an unresolved human-approval loop (so follow-ups like
    "it's approved, go ahead" stay with the Tier-2 agent).
    """
    if not payload:
        return False
    if any(kw in _latest_text(payload) for kw in ESCALATION_KEYWORDS):
        return True
    try:
        from src.observability.request_context import get_session_id
        return _has_open_approval_loop(get_session_id())
    except Exception:
        return False


def is_tier1_query(payload: object) -> bool:
    return not is_escalation_query(payload)


class TriageExecutor(af.Executor):
    """Pass-through router: wraps input as an agent request and forwards it.

    Exactly one conditional edge matches, so the request reaches either the
    Tier-2 escalation agent or the Tier-1 support agent. Uses send_message —
    yield_output would complete the workflow without reaching any agent.
    """

    @af.handler
    async def process(
        self, messages: list[af.Message], ctx: af.WorkflowContext[af.AgentExecutorRequest]
    ) -> None:
        await ctx.send_message(
            af.AgentExecutorRequest(messages=list(messages), should_respond=True)
        )


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

        self._client = OpenAIChatCompletionClient(
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
            disable_web_search=True,   # Groq rejects web_search_options
            disable_file_memory=True,  # SQLite history provider is the single source of truth
            disable_todo=True,         # Groq rejects malformed calls to built-in todo tools
            disable_mode=True,
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

    def _persist_turn(self, session_id: str, role: str, text: str) -> None:
        """Append one transcript turn to SQLite (idempotent per payload)."""
        try:
            msg = af.Message(role=role, contents=[text], author_name=role)
            from src.persistence.repositories import SessionRepository
            SessionRepository.save_messages(session_id, [msg.to_json()])
        except Exception as exc:
            log.warning("transcript_persist_failed", session_id=session_id, error=str(exc))

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
            # Persist the user turn (application-owned durable transcript).
            self._persist_turn(session_id, role="user", text=message)

            response: af.AgentResponse = await agent.run(
                messages=message,
                session=session,
                client_kwargs={"session": session},
            )

            reply_text: str = response.text or "(no response)"

            # Persist the assistant turn so /sessions/{id}/history and UI
            # restore work independently of framework-internal state.
            self._persist_turn(session_id, role="assistant", text=reply_text)

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
