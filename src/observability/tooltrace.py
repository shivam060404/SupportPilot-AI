"""
src/observability/tooltrace.py
──────────────────────────────
Per-request tool-call trace collector.

The chat route opens a trace scope before invoking the agent; every wrapped
tool appends an event (name, redacted args, duration, status). The route then
returns the trace in the API response so the UI can show exactly what the
agent did — the "explainable interaction" requirement from the spec.
"""
from __future__ import annotations

import time
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

_trace_events: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar(
    "tool_trace_events", default=None
)

# Keys whose values must never be echoed into traces/logs.
_REDACTED_KEYS = {"password", "secret", "token", "api_key", "credential"}


def start_tool_trace() -> None:
    _trace_events.set([])


def stop_tool_trace() -> List[Dict[str, Any]]:
    """Close the scope and return collected events."""
    events = _trace_events.get() or []
    _trace_events.set(None)
    return events


def record_event(event: Dict[str, Any]) -> None:
    events = _trace_events.get()
    if events is not None:
        events.append(event)


def get_tool_trace() -> List[Dict[str, Any]]:
    return list(_trace_events.get() or [])


# ── Structured artifacts (e.g. RAG sources) attached during a request ────────
_artifacts: ContextVar[Optional[Dict[str, List[Any]]]] = ContextVar(
    "tool_trace_artifacts", default=None
)


def start_artifacts() -> None:
    _artifacts.set({})


def collect_artifacts() -> Dict[str, List[Any]]:
    artifacts = _artifacts.get() or {}
    _artifacts.set(None)
    return artifacts


def record_artifact(kind: str, items: List[Any]) -> None:
    store = _artifacts.get()
    if store is None:
        return
    store.setdefault(kind, []).extend(items)


def redact_args(args: Dict[str, Any]) -> Dict[str, Any]:
    safe: Dict[str, Any] = {}
    for key, value in (args or {}).items():
        if any(marker in key.lower() for marker in _REDACTED_KEYS):
            safe[key] = "***"
        else:
            text = str(value)
            safe[key] = text if len(text) <= 200 else text[:200] + "…"
    return safe


class traced_tool:
    """Decorator that records timing/status of a tool invocation.

    Applied *under* @af.tool so MAF still sees the original callable surface.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            started = time.perf_counter()
            arg_names = getattr(func, "__code__", None) and func.__code__.co_varnames or []
            payload = {k: v for k, v in zip(arg_names, args)}
            payload.update(kwargs)
            record_event({
                "tool": self.name,
                "args": redact_args(payload),
                "phase": "started",
                "ts": round(time.perf_counter(), 3),
            })
            try:
                result = func(*args, **kwargs)
                record_event({
                    "tool": self.name,
                    "phase": "finished",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "ok": True,
                })
                return result
            except Exception as exc:
                record_event({
                    "tool": self.name,
                    "phase": "failed",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    "ok": False,
                    "error": str(exc)[:200],
                })
                raise

        wrapper.__name__ = getattr(func, "__name__", self.name)
        wrapper.__doc__ = getattr(func, "__doc__", None)
        wrapper.__signature__ = getattr(func, "__signature__", None)
        import inspect
        try:
            wrapper.__signature__ = inspect.signature(func)
        except (TypeError, ValueError):
            pass
        return wrapper
