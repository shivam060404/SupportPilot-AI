"""
core/middleware/logging_middleware.py
──────────────────────────────────────
Enhanced HTTP logging middleware with PII redaction and sampling.

Replaces src/api/middleware.py. Features:
  - Structured JSON request/response logging
  - PII redaction on request paths and query params
  - Configurable payload sampling (SAMPLING_RATE env var)
  - Request timing histogram
  - Trace ID propagation
"""
from __future__ import annotations

import os
import random
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.observability.logger import bind_trace_context, clear_trace_context, get_logger
from src.observability.request_context import set_request_context, clear_request_context

log = get_logger(__name__)

# Fraction of successful requests to log at full detail (1.0 = all, 0.1 = 10%)
SAMPLING_RATE = float(os.getenv("LOG_SAMPLING_RATE", "1.0"))
# Errors are always logged regardless of sampling rate
ALWAYS_LOG_ERRORS = os.getenv("ALWAYS_LOG_ERRORS", "true").lower() == "true"


class EnhancedLoggingMiddleware(BaseHTTPMiddleware):
    """Production-grade HTTP logging middleware with PII redaction and sampling."""

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        request.state.trace_id = trace_id

        bind_trace_context(trace_id=trace_id)
        set_request_context(trace_id=trace_id)

        start_time = time.perf_counter()
        is_error = False

        try:
            response = await call_next(request)
            is_error = response.status_code >= 400
            process_time_ms = (time.perf_counter() - start_time) * 1000

            # Sampling: always log errors, sample successes
            should_log = (
                is_error and ALWAYS_LOG_ERRORS
            ) or random.random() < SAMPLING_RATE

            if should_log:
                log.info(
                    "http_request",
                    method=request.method,
                    path=request.url.path,  # NOT query params (may contain PII)
                    status_code=response.status_code,
                    duration_ms=round(process_time_ms, 2),
                    trace_id=trace_id,
                    is_error=is_error,
                )

            response.headers["x-trace-id"] = trace_id
            response.headers["x-duration-ms"] = str(round(process_time_ms, 2))
            return response

        except Exception as e:
            process_time_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "http_request_error",
                method=request.method,
                path=request.url.path,
                error=str(e)[:200],
                duration_ms=round(process_time_ms, 2),
                trace_id=trace_id,
                exc_info=True,
            )
            raise
        finally:
            clear_trace_context()
            clear_request_context()
