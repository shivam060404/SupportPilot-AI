"""
src/observability/metrics.py
─────────────────────────────
Prometheus-compatible metrics for SupportPilot AI.

Metrics are collected using simple in-memory counters/histograms.
The /metrics endpoint (if enabled) exports them in Prometheus text format.

If prometheus_client is not installed, all operations are no-ops.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional

# Try to import prometheus_client; degrade gracefully if missing
try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, REGISTRY
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


# ── Metrics definitions ───────────────────────────────────────────────────────

class _NoopMetric:
    """No-op metric for when prometheus_client is not installed."""
    def labels(self, **kwargs): return self
    def inc(self, amount=1): pass
    def observe(self, value): pass
    def set(self, value): pass


if _PROMETHEUS_AVAILABLE:
    _request_duration = Histogram(
        "supportpilot_request_duration_seconds",
        "End-to-end request duration",
        buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    )
    _tool_calls_total = Counter(
        "supportpilot_tool_calls_total",
        "Total tool invocations",
        ["tool_name", "status"],
    )
    _guardrail_violations_total = Counter(
        "supportpilot_guardrail_violations_total",
        "Total guardrail violations",
        ["guardrail", "category", "severity"],
    )
    _rag_retrieval_score = Histogram(
        "supportpilot_rag_retrieval_score",
        "RAG retrieval relevance score",
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
    _active_sessions = Gauge(
        "supportpilot_active_sessions",
        "Number of active chat sessions",
    )
    _llm_tokens_total = Counter(
        "supportpilot_llm_tokens_total",
        "Estimated LLM token usage",
        ["direction"],  # "input" or "output"
    )
    _guardrail_pipeline_duration = Histogram(
        "supportpilot_guardrail_pipeline_duration_seconds",
        "Guardrail pipeline duration",
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
    )
else:
    _request_duration = _NoopMetric()
    _tool_calls_total = _NoopMetric()
    _guardrail_violations_total = _NoopMetric()
    _rag_retrieval_score = _NoopMetric()
    _active_sessions = _NoopMetric()
    _llm_tokens_total = _NoopMetric()
    _guardrail_pipeline_duration = _NoopMetric()


# ── Public API ────────────────────────────────────────────────────────────────

@contextmanager
def track_request_duration():
    """Context manager to track end-to-end request latency."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if _PROMETHEUS_AVAILABLE:
            _request_duration.observe(duration)


def record_tool_call(tool_name: str, success: bool) -> None:
    status = "success" if success else "error"
    if _PROMETHEUS_AVAILABLE:
        _tool_calls_total.labels(tool_name=tool_name, status=status).inc()


def record_guardrail_violation(guardrail: str, category: str, severity: str) -> None:
    if _PROMETHEUS_AVAILABLE:
        _guardrail_violations_total.labels(
            guardrail=guardrail, category=category, severity=severity
        ).inc()


def record_rag_score(score: float) -> None:
    if _PROMETHEUS_AVAILABLE and score is not None:
        _rag_retrieval_score.observe(score)


def set_active_sessions(count: int) -> None:
    if _PROMETHEUS_AVAILABLE:
        _active_sessions.set(count)


def record_llm_tokens(input_tokens: int = 0, output_tokens: int = 0) -> None:
    if _PROMETHEUS_AVAILABLE:
        if input_tokens:
            _llm_tokens_total.labels(direction="input").inc(input_tokens)
        if output_tokens:
            _llm_tokens_total.labels(direction="output").inc(output_tokens)


@contextmanager
def track_guardrail_pipeline():
    """Context manager to track guardrail pipeline duration."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if _PROMETHEUS_AVAILABLE:
            _guardrail_pipeline_duration.observe(duration)


def get_metrics_text() -> str:
    """Export metrics in Prometheus text format."""
    if not _PROMETHEUS_AVAILABLE:
        return "# Prometheus client not installed. pip install prometheus-client\n"
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest().decode("utf-8")
