"""
src/observability/logger.py
────────────────────────────
Structured JSON logger built on structlog.

Usage
-----
    from src.observability.logger import get_logger
    log = get_logger(__name__)
    log.info("agent_response", session_id="abc", tokens=42)

Each log record includes:
  - timestamp (ISO 8601 UTC)
  - level
  - logger name
  - correlation/trace_id (if set via context)
  - arbitrary key-value pairs
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from config import get_settings

_configured = False


def configure_logging() -> None:
    """Call once at application startup."""
    global _configured
    if _configured:
        return
    _configured = True

    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Standard library root logger
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.app_env == "development":
        # Human-readable in dev
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # JSON in production / CI
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named, pre-configured structlog logger."""
    configure_logging()
    return structlog.get_logger(name)


def bind_trace_context(trace_id: str, session_id: str | None = None) -> None:
    """Bind correlation IDs to the structlog context for this async task."""
    ctx: dict[str, str] = {"trace_id": trace_id}
    if session_id:
        ctx["session_id"] = session_id
    structlog.contextvars.bind_contextvars(**ctx)


def clear_trace_context() -> None:
    """Clear correlation IDs from the structlog context."""
    structlog.contextvars.clear_contextvars()
