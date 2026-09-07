"""
src/observability/tracing.py
─────────────────────────────
OpenTelemetry distributed tracing integration.

Creates spans for:
  - Full HTTP request lifecycle
  - Agent execution (MAF run)
  - Individual tool calls
  - RAG retrieval pipeline
  - Guardrail checks

Degrades gracefully if opentelemetry is not installed.

Usage:
    from src.observability.tracing import tracer, start_span

    with start_span("agent.run") as span:
        span.set_attribute("session_id", session_id)
        result = await agent.chat(message)
"""
from __future__ import annotations

import contextlib
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

# Graceful degradation if opentelemetry not installed
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource

    _resource = Resource.create({"service.name": "supportpilot-ai", "service.version": "7.0"})
    _provider = TracerProvider(resource=_resource)
    _provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(_provider)
    tracer = trace.get_tracer("supportpilot.ai")
    _OTEL_AVAILABLE = True
except ImportError:
    tracer = None
    _OTEL_AVAILABLE = False


class _NoopSpan:
    """No-op span for when OpenTelemetry is not available."""
    def set_attribute(self, key: str, value: Any) -> None: pass
    def set_status(self, *args, **kwargs) -> None: pass
    def record_exception(self, exc: Exception) -> None: pass
    def __enter__(self): return self
    def __exit__(self, *args): pass


@contextmanager
def start_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
) -> Generator[Any, None, None]:
    """
    Start a tracing span. No-op if OTel is not installed.

    Usage:
        with start_span("rag.retrieve", {"query": query}) as span:
            results = retriever.search(query)
    """
    if not _OTEL_AVAILABLE or tracer is None:
        yield _NoopSpan()
        return

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                try:
                    span.set_attribute(k, str(v)[:500] if v is not None else "")
                except Exception:
                    pass
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            raise


def get_current_trace_id() -> Optional[str]:
    """Get the current OTel trace ID as a hex string."""
    if not _OTEL_AVAILABLE:
        return None
    try:
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return None
