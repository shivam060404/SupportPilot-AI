"""
core/middleware/rate_limiter.py
────────────────────────────────
Per-session sliding-window rate limiter middleware.

Limits:
  - MAX_MESSAGES_PER_MINUTE: 30 (configurable via env)
  - MAX_MESSAGES_PER_HOUR: 200 (configurable via env)

Returns 429 with Retry-After header when limit is exceeded.
Uses an in-memory store (suitable for single-process; upgrade to Redis for multi-process).
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.observability.logger import get_logger

log = get_logger(__name__)

MAX_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
MAX_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "200"))

# Rate-limited paths only (don't limit health, static, tickets, etc.)
RATE_LIMITED_PATHS = {"/chat", "/api/chat"}


class _SlidingWindowStore:
    """Thread-safe in-memory sliding window counter."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._minute_windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._hour_windows: Dict[str, Deque[float]] = defaultdict(deque)

    def is_allowed(self, session_id: str) -> tuple[bool, int]:
        """
        Check if session is within limits.
        Returns (allowed, retry_after_seconds).
        """
        now = time.time()
        minute_cutoff = now - 60
        hour_cutoff = now - 3600

        with self._lock:
            m_dq = self._minute_windows[session_id]
            h_dq = self._hour_windows[session_id]

            # Evict old entries
            while m_dq and m_dq[0] < minute_cutoff:
                m_dq.popleft()
            while h_dq and h_dq[0] < hour_cutoff:
                h_dq.popleft()

            if len(m_dq) >= MAX_PER_MINUTE:
                retry_after = int(m_dq[0] + 60 - now) + 1
                return False, retry_after

            if len(h_dq) >= MAX_PER_HOUR:
                retry_after = int(h_dq[0] + 3600 - now) + 1
                return False, retry_after

            m_dq.append(now)
            h_dq.append(now)
            return True, 0


_store = _SlidingWindowStore()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware enforcing per-session rate limits on chat endpoints."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path not in RATE_LIMITED_PATHS:
            return await call_next(request)

        # Extract session_id from body (best-effort; falls back to IP)
        session_id = request.headers.get("x-session-id") or str(request.client.host)

        allowed, retry_after = _store.is_allowed(session_id)
        if not allowed:
            log.warning(
                "rate_limit_exceeded",
                session_id=session_id,
                retry_after=retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Please wait {retry_after} seconds.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
