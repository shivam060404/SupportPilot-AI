"""
src/agents/supervisor_agent.py
──────────────────────────────
Orchestrates the SupportPilot AI MAF workflow.

This has been refactored to use the new `core/orchestration` components
for routing and client instantiation.
"""
import uuid
from typing import Optional

import agent_framework as af

from config import get_settings
from core.orchestration.providers.history_provider import SQLiteHistoryProvider
from core.orchestration.agents.tier2_agent import create_escalation_agent
from core.orchestration.prompts.tier1_prompt import SYSTEM_PROMPT
from src.tools.search_knowledge_base import search_knowledge_base
from src.tools.check_service_status import check_service_status
from src.tools.create_ticket import create_ticket
from src.tools.get_ticket_status import get_ticket_status
from src.observability.logger import get_logger
from src.persistence.database import init_db
from core.orchestration.router import is_escalation_query, is_tier1_query
from core.orchestration.providers.groq_client import create_groq_client

log = get_logger(__name__)


class TriageExecutor(af.Executor):
    """Pass-through router: wraps input as an agent request and forwards it."""

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
    workflow.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # Ensure schema exists.
        init_db()

        self.llm_ready = bool(settings.groq_api_key)
        self._client = None
        self.workflow_agent = None
        self._history_provider = SQLiteHistoryProvider()

        if not self.llm_ready:
            log.error("support_agent_init_no_api_key")
            return

        # Use our clean Groq client factory
        self._client = create_groq_client(
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
            disable_web_search=True,
            disable_file_memory=True,
            disable_todo=True,
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

    async def chat(self, message: str, session_id: str) -> dict:
        """
        Send a user message to the MAF workflow and return a structured result.
        Called by the guardrail pipeline.
        """
        if not self.llm_ready or self.workflow_agent is None:
            raise RuntimeError("GROQ_API_KEY is not configured.")

        agent, session = self._get_or_create_session(session_id)

        try:
            # Persist the user turn
            self._persist_turn(session_id, role="user", text=message)

            response: af.AgentResponse = await agent.run(
                messages=message,
                session=session,
                client_kwargs={"session": session},
            )

            reply_text: str = response.text or "(no response)"

            # Persist the assistant turn
            self._persist_turn(session_id, role="assistant", text=reply_text)

            # Retrieve RAG sources from tool trace artifacts if available
            from src.observability.tooltrace import collect_artifacts
            artifacts = collect_artifacts()
            rag_sources = artifacts.get("rag_sources", [])

            return {
                "session_id": session_id,
                "response": reply_text,
                "rag_sources": rag_sources,
            }

        except Exception as exc:
            log.error(
                "agent_chat_error",
                session_id=session_id,
                error=str(exc),
                exc_info=True,
            )
            raise
