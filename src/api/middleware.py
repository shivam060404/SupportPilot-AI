"""
src/api/middleware.py
─────────────────────
FastAPI middleware for observability.
"""
from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.observability.logger import bind_trace_context, clear_trace_context, get_logger

log = get_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        
        # We can extract session_id from body if we wanted to read it, but for a middleware
        # it's better to just bind the trace_id.
        bind_trace_context(trace_id=trace_id)
        
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Log the successful request
            log.info(
                "http_request",
                method=request.method,
                url=str(request.url.path),
                status_code=response.status_code,
                duration_ms=round(process_time_ms, 2),
            )
            
            response.headers["x-trace-id"] = trace_id
            return response
            
        except Exception as e:
            process_time_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "http_request_error",
                method=request.method,
                url=str(request.url.path),
                error=str(e),
                duration_ms=round(process_time_ms, 2),
                exc_info=True
            )
            raise
        finally:
            clear_trace_context()
