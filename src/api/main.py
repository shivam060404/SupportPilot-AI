"""
src/api/main.py
────────────────
FastAPI application entry point for SupportPilot AI.

Architecture
────────────
Browser UI  →  FastAPI  →  MAF Agent  →  Groq LLaMA
                              ↓
                     (Phase 2+: RAG / Tools / MCP)

Startup
───────
On startup the app creates a single SupportAgent instance and stores it in
app.state so route handlers can access it without global state.

Run locally
───────────
    uvicorn src.api.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from src.api.routes.chat import router as chat_router
from src.api.routes.tickets import router as tickets_router
from src.api.routes.sessions import router as sessions_router
from src.api.routes.services import router as services_router
from src.api.routes.approvals import router as approvals_router
from src.observability.logger import configure_logging, get_logger
from src.persistence.database import init_db

log = get_logger(__name__)
settings = get_settings()

# ── Static files path ─────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


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
    init_db()

    # Ensure the knowledge base exists so RAG works out of the box
    # (fresh deploys / Docker volumes start empty).
    try:
        from src.rag.retriever import KnowledgeRetriever
        if not KnowledgeRetriever().available:
            from src.rag.ingestor import ingest_knowledge_base
            log.info("kb_auto_ingest_start")
            ingest_knowledge_base()
    except Exception as exc:
        # Non-fatal: agent still answers without grounded retrieval.
        log.error("kb_auto_ingest_failed", error=str(exc))

    from core.orchestration.agents.tier1_agent import SupportAgent
    app.state.agent = SupportAgent()

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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

from core.middleware.logging_middleware import EnhancedLoggingMiddleware
from core.middleware.rate_limiter import RateLimiterMiddleware
from core.middleware.auth import APIKeyAuthMiddleware

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

# ── Static files (web UI) ─────────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Root → serve Web UI ───────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request) -> HTMLResponse:
    """Serve the browser chat UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(
        content="<h1>SupportPilot AI</h1><p>UI not found. Run from project root.</p>"
    )


# ── Metrics ───────────────────────────────────────────────────────────────────
from src.observability.metrics import get_metrics_text
from fastapi.responses import PlainTextResponse

@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics_text()
