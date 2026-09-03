"""
core/middleware/auth.py
────────────────────────
Optional API key authentication for REST endpoints.

Configuration:
  - API_KEY_REQUIRED=true/false (default: false in development)
  - API_KEY=<secret-key>

When enabled, all requests to protected endpoints must include:
  Authorization: Bearer <api-key>
  or
  X-API-Key: <api-key>

Public paths (health, static) are always allowed.
"""
from __future__ import annotations

import os
from typing import Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.observability.logger import get_logger

log = get_logger(__name__)

API_KEY_REQUIRED = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
API_KEY = os.getenv("API_KEY", "")

# Paths that never require authentication
PUBLIC_PATHS: Set[str] = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}

PUBLIC_PREFIXES = ("/static",)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Optional API key authentication middleware."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip auth when disabled
        if not API_KEY_REQUIRED:
            return await call_next(request)

        path = request.url.path

        # Always allow public paths and prefixes
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Extract API key from headers
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:].strip()
        else:
            provided_key = request.headers.get("X-API-Key", "").strip()

        if not provided_key or provided_key != API_KEY:
            log.warning(
                "auth_failed",
                path=path,
                method=request.method,
                has_key=bool(provided_key),
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized. Provide a valid API key."},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
