"""
core/guardrails/pipeline.py
────────────────────────────
GuardrailPipeline: Orchestrates input and output guardrails.

Flow:
  1. Input pipeline: run all input guardrails in order
     - Short-circuit on CRITICAL/HIGH violations (block request)
     - Accumulate MEDIUM/LOW violations (continue with sanitized content)
  2. Agent execution (provided as a callable by the caller)
  3. Output pipeline: run all output guardrails on the response
     - Always sanitize; block only on extreme policy violations

All guardrail decisions are audit-logged.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

from core.guardrails.base import GuardrailBase, GuardrailResult, ViolationSeverity
from core.guardrails.input.pii_detector import PIIDetectorGuardrail
from core.guardrails.input.prompt_injection import PromptInjectionGuardrail
from core.guardrails.input.prompt_safety import PromptSafetyGuardrail
from core.guardrails.input.input_validation import InputValidationGuardrail
from core.guardrails.input.contextual_compliance import ContextualComplianceGuardrail
from core.guardrails.output.content_moderation import ContentModerationGuardrail
from core.guardrails.output.pii_leakage import PIILeakageGuardrail
from core.guardrails.output.hallucination_check import HallucinationCheckGuardrail
from core.guardrails.output.output_validation import OutputValidationGuardrail
from src.observability.logger import get_logger

log = get_logger(__name__)


@dataclass
class PipelineResult:
    """Combined result of the full guardrail pipeline."""
    blocked: bool
    input_violations: List[Any] = field(default_factory=list)
    output_violations: List[Any] = field(default_factory=list)
    sanitized_input: Optional[str] = None
    sanitized_output: Optional[str] = None
    block_reason: Optional[str] = None
    user_block_message: Optional[str] = None
    pii_detected: bool = False
    pii_types: List[str] = field(default_factory=list)
    grounding_metadata: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


class GuardrailPipeline:
    """
    Orchestrates all input and output guardrails around agent execution.

    Usage:
        pipeline = GuardrailPipeline()
        result = await pipeline.run(
            message="My VPN is broken",
            agent_fn=async lambda msg: agent.chat(msg),
        )
    """

    def __init__(self) -> None:
        # Input guardrails — order matters! (validation → injection → safety → pii → scope)
        self.input_guardrails: List[GuardrailBase] = [
            InputValidationGuardrail(),
            PromptInjectionGuardrail(),
            PromptSafetyGuardrail(),
            PIIDetectorGuardrail(),
            ContextualComplianceGuardrail(),
        ]

        # Output guardrails — always run on agent response
        self.output_guardrails: List[GuardrailBase] = [
            OutputValidationGuardrail(),
            PIILeakageGuardrail(),
            ContentModerationGuardrail(),
            HallucinationCheckGuardrail(),
        ]

    async def run(
        self,
        message: str,
        agent_fn: Callable[[str], Coroutine[Any, Any, Dict[str, Any]]],
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> tuple[PipelineResult, Optional[Dict[str, Any]]]:
        """
        Run the full guardrail pipeline.

        Returns:
            (PipelineResult, agent_result | None)
            agent_result is None if the request was blocked.
        """
        started = time.perf_counter()
        ctx = context or {}

        # ── INPUT PHASE ──────────────────────────────────────────────────────
        sanitized_message = message
        all_input_violations = []
        pii_types: List[str] = []

        for guardrail in self.input_guardrails:
            result: GuardrailResult = guardrail.check(sanitized_message, ctx)

            if result.sanitized_content is not None:
                sanitized_message = result.sanitized_content

            all_input_violations.extend(result.violations)

            # Collect PII metadata
            if guardrail.name == "pii_detector" and not result.passed is False:
                for v in result.violations:
                    pii_types.extend(v.details.get("pii_types", []))

            # Short-circuit on block-level violations
            if result.is_blocked:
                duration = (time.perf_counter() - started) * 1000
                log.warning(
                    "guardrail_input_blocked",
                    session_id=session_id,
                    guardrail=guardrail.name,
                    category=result.violations[0].category if result.violations else "unknown",
                    duration_ms=round(duration, 1),
                )
                self._audit_block(guardrail.name, result, session_id)
                return PipelineResult(
                    blocked=True,
                    input_violations=all_input_violations,
                    sanitized_input=sanitized_message,
                    block_reason=f"{guardrail.name}: {result.violations[0].category}",
                    user_block_message=result.user_facing_block_message(),
                    pii_detected=bool(pii_types),
                    pii_types=pii_types,
                    duration_ms=round(duration, 1),
                ), None

            # Log non-blocking violations at appropriate level
            for v in result.violations:
                if v.severity == ViolationSeverity.MEDIUM:
                    log.info(
                        "guardrail_input_warning",
                        session_id=session_id,
                        guardrail=v.guardrail,
                        category=v.category,
                        severity=v.severity.value,
                    )

        log.debug(
            "guardrail_input_passed",
            session_id=session_id,
            violations=len(all_input_violations),
            pii_types=pii_types,
        )

        # ── AGENT EXECUTION ──────────────────────────────────────────────────
        agent_result = await agent_fn(sanitized_message)
        response_text: str = agent_result.get("response", "") if agent_result else ""

        # ── OUTPUT PHASE ─────────────────────────────────────────────────────
        # Build context with RAG sources for hallucination check
        out_ctx = {**ctx, "rag_sources": agent_result.get("rag_sources", []) if agent_result else []}
        sanitized_output = response_text
        all_output_violations = []
        grounding_meta: Dict[str, Any] = {}

        for guardrail in self.output_guardrails:
            result = guardrail.check(sanitized_output, out_ctx)

            if result.sanitized_content is not None:
                sanitized_output = result.sanitized_content

            all_output_violations.extend(result.violations)

            if guardrail.name == "hallucination_check":
                grounding_meta = result.metadata

            if result.is_blocked:
                duration = (time.perf_counter() - started) * 1000
                log.warning(
                    "guardrail_output_blocked",
                    session_id=session_id,
                    guardrail=guardrail.name,
                    duration_ms=round(duration, 1),
                )
                # For output blocks, return the fallback message (not an error)
                if agent_result:
                    agent_result["response"] = sanitized_output or result.user_facing_block_message()
                return PipelineResult(
                    blocked=False,  # Not blocking the user, just replacing response
                    input_violations=all_input_violations,
                    output_violations=all_output_violations,
                    sanitized_input=sanitized_message,
                    sanitized_output=sanitized_output,
                    pii_detected=bool(pii_types),
                    pii_types=pii_types,
                    grounding_metadata=grounding_meta,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                ), agent_result

        # Update agent result with sanitized response
        if agent_result:
            agent_result["response"] = sanitized_output

        duration = round((time.perf_counter() - started) * 1000, 1)
        log.debug(
            "guardrail_pipeline_complete",
            session_id=session_id,
            input_violations=len(all_input_violations),
            output_violations=len(all_output_violations),
            duration_ms=duration,
        )

        return PipelineResult(
            blocked=False,
            input_violations=all_input_violations,
            output_violations=all_output_violations,
            sanitized_input=sanitized_message,
            sanitized_output=sanitized_output,
            pii_detected=bool(pii_types),
            pii_types=pii_types,
            grounding_metadata=grounding_meta,
            duration_ms=duration,
        ), agent_result

    def _audit_block(
        self,
        guardrail_name: str,
        result: GuardrailResult,
        session_id: Optional[str],
    ) -> None:
        """Write a guardrail block event to the audit log."""
        try:
            from src.persistence.repositories import AuditLogRepository
            violation = result.violations[0] if result.violations else None
            AuditLogRepository.log_action(
                action="guardrail_block",
                details={
                    "guardrail": guardrail_name,
                    "category": violation.category if violation else "unknown",
                    "severity": violation.severity.value if violation else "unknown",
                },
                session_id=session_id,
            )
        except Exception as exc:
            log.error("audit_guardrail_block_failed", error=str(exc))
