"""
backend/app/api/main.py
────────────────
FastAPI application entry point for SupportPilot AI.

Architecture
────────────
Browser UI  →  FastAPI  →  MAF Agent  →  Groq LLaMA
                              ↓
                     (Phase 2+: RAG / Tools / MCP)

Startup
───────
On startup the app creates a single KnowledgeableITSupportAgent instance and stores it in
app.state so route handlers can access it without global state.

Run locally
───────────
    uvicorn backend.app.api.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from backend.app.core.config import get_settings
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.tickets import router as tickets_router
from backend.app.api.routes.sessions import router as sessions_router
from backend.app.api.routes.services import router as services_router
from backend.app.api.routes.approvals import router as approvals_router
from backend.app.observability.logger import configure_logging, get_logger
from backend.app.persistence.database import check_database_connection

log = get_logger(__name__)
settings = get_settings()

# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info(
        "supportpilot_startup",
        app=settings.app_name,
        env=settings.app_env,
        model=settings.groq_model,
        phase="Phase 6",
    )

    # Ensure DB schema exists, then initialise the MAF agent once and share it
    check_database_connection()

    # Ensure the knowledge base exists so RAG works out of the box
    # (fresh deploys / Docker volumes start empty).
    try:
        from backend.app.ai.rag.retriever import KnowledgeRetriever
        if not KnowledgeRetriever().available:
            from backend.app.ai.rag.ingestor import ingest_knowledge_base
            log.info("kb_auto_ingest_start")
            ingest_knowledge_base()
    except Exception as exc:
        # Non-fatal: agent still answers without grounded retrieval.
        log.error("kb_auto_ingest_failed", error=str(exc))

    from backend.app.ai.agents.knowledgeable_it_support_agent import KnowledgeableITSupportAgent
    app.state.agent = KnowledgeableITSupportAgent()

    yield

    log.info("supportpilot_shutdown")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SupportPilot AI",
    description=(
        "AI-powered IT Support Agent built with Microsoft Agent Framework (MAF), "
        "Groq LLaMA, FastAPI, and RAG. Phase 6: Tests/Observability/Docker."
    ),
    version="1.0.0-phase6",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

from backend.app.core.middleware.logging_middleware import EnhancedLoggingMiddleware
from backend.app.core.middleware.rate_limiter import RateLimiterMiddleware
from backend.app.core.middleware.auth import APIKeyAuthMiddleware

# ── CORS & Middleware ─────────────────────────────────────────────────────────
app.add_middleware(EnhancedLoggingMiddleware)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(APIKeyAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(chat_router, prefix="/api/v1")
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(services_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")

# ── Root service information ──────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request) -> HTMLResponse:
    """Provide a small service landing response; the UI is served by Next.js."""
    return HTMLResponse(content="<h1>SupportPilot AI API</h1><p>Use the Next.js frontend.</p>")


# ── Metrics ───────────────────────────────────────────────────────────────────
from backend.app.observability.metrics import get_metrics_text
from fastapi.responses import PlainTextResponse

@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_text()
