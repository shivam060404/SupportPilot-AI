"""
src/observability/request_context.py
────────────────────────────────────
Request-scoped correlation context (contextvar based).

The API layer sets session_id / trace_id per request; deterministic code
(tools, repositories, guards) reads them so the LLM never needs to pass
identity information around.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def set_request_context(session_id: Optional[str] = None, trace_id: Optional[str] = None) -> None:
    if session_id is not None:
        _session_id.set(session_id)
    if trace_id is not None:
        _trace_id.set(trace_id)


def clear_request_context() -> None:
    _session_id.set(None)
    _trace_id.set(None)


def get_session_id() -> Optional[str]:
    return _session_id.get()


def get_trace_id() -> Optional[str]:
    return _trace_id.get()
