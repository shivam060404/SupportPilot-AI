# SupportPilot AI

> **AI-powered IT Support Agent** built with **Microsoft Agent Framework (MAF) 1.14.0**, Groq (`openai/gpt-oss-120b`), FastAPI, RAG, MCP, and a code-enforced human-approval gate.

```
Browser Chat UI (approvals panel, tool/source rendering)
      ↓
    FastAPI  ── REST: chat · tickets · sessions · services · approvals
      ↓
Microsoft Agent Framework WorkflowBuilder (deterministic routing)
      ↙                              ↘
Tier-1 IT Agent                  Tier-2 Escalation Agent
RAG · service status · tickets   MCP AD lookups + approval-gate tools
      │                               │
      └─────── Input Guardrails ──────┘ (PII redaction, prompt injection)
      ↘                              ↙
        Groq openai/gpt-oss-120b (OpenAI-compatible chat-completions endpoint)
                     ↓
     SQLite (tickets · audit log · transcripts · approvals)
     ChromaDB (knowledge-base vectors)
```

## Human-in-the-loop by design

Sensitive actions (e.g. `unlock_account`) are **never** reachable by the LLM directly:

1. The Tier-2 agent calls `request_approval` → a `PENDING` record is stored and audited.
2. A human approves/rejects via the UI panel or `POST /api/v1/approvals/{id}/approve|reject`.
3. Only `execute_approved_action` can run the capability — it independently verifies a matching `APPROVED` record in the database before touching the business service. Mismatched targets, replays (`ALREADY_EXECUTED`), rejections and unapproved attempts are all blocked and audit-logged.

The sensitive capability is deliberately **not** exposed on the MCP server; enforcement lives outside the LLM.

### Sticky escalation routing

Routing is deterministic keyword pre-triage **plus** a sticky rule: while a session has an unresolved approval request (`PENDING` or `APPROVED`-not-yet-executed), all follow-up messages stay with the Tier-2 agent — so natural phrasing like *"it's approved, go ahead"* correctly triggers the guarded execution instead of falling back to Tier 1.

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- A free [Groq API key](https://console.groq.com)

### 2. Set up environment

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set your real GROQ_API_KEY
```

Without a key the server still boots — chat returns a clear configuration error while every other endpoint works.

### 4. Run

```bash
# Using the virtual environment directly:
.venv/bin/python -m uvicorn src.api.main:app --reload --port 8000

# Or after activating .venv:
source .venv/bin/activate
uvicorn src.api.main:app --reload --port 8000
```

On startup the app auto-ingests `knowledge_base/` into ChromaDB if the vector store is empty. To force a re-index after editing articles:

```bash
python -m src.rag.ingestor
```

### 5. Open the chat UI

Visit **http://localhost:8000**. Conversations survive page reloads (session restore via the history API) and every turn is durably transcripted to SQLite.

**Try the approval flow:** ask *"My AD account is locked, please unlock it"* → the Tier-2 agent investigates via MCP, files an approval request, and pauses. A red bell appears in the header — approve it, then say *"it's approved, go ahead"*. The agent verifies the approval and executes.

> **Model note:** `GROQ_MODEL` defaults to `openai/gpt-oss-120b`. The older `llama-3.3-70b-versatile` ID has been retired from Groq's catalog; any current chat model with tool-calling support works.

---

## Live-verified behaviour (real Groq calls)

| Scenario | Verified result |
|----------|-----------------|
| Tier-1 VPN issue | Calls `search_knowledge_base`, cites *VPN Troubleshooting Guide* with relevance scores |
| Multi-turn follow-up | Remembers prior turns from SQLite-backed transcript + session state |
| Ticket creation | Returns a real ticket ID, retrievable via `GET /tickets/{id}` |
| Service status | Reads the allow-listed registry (Salesforce → Outage), never invents status |
| Account lockout | Routed to Tier-2, verified via MCP, files `request_approval`, stops and waits |
| Human approves in UI/REST | Sticky routing keeps Tier-2; `execute_approved_action` validates and executes |
| Unapproved execution attempt | Blocked (`DENIED` / `ALREADY_EXECUTED`) and written to the audit log |

## Known limitations

- Latency ranges ~2–60s per reply depending on tool-loop depth.
- Agent *context* across server restarts is best-effort (framework-managed); transcripts are always durable in SQLite. Full restart-resilient context would use MAF workflow checkpointing.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Browser chat UI |
| `/api/v1/chat` | POST | Send a message to the agent (returns reply + tool trace + RAG sources) |
| `/api/v1/health` | GET | Liveness check |
| `/api/v1/tickets` | GET/POST | List / create tickets |
| `/api/v1/tickets/{id}` | GET | Ticket details |
| `/api/v1/sessions/{id}/history` | GET | Chat history for a session |
| `/api/v1/services/status` | GET | Status of allow-listed services |
| `/api/v1/approvals` | GET | List approvals (filter by `status`, `session_id`) |
| `/api/v1/approvals/{id}` | GET | Approval details |
| `/api/v1/approvals/{id}/approve` | POST | **Human** grants approval |
| `/api/v1/approvals/{id}/reject` | POST | **Human** rejects approval |
| `/api/docs` | GET | Swagger UI |

### POST /api/v1/chat

```json
// Request
{
  "message": "My VPN keeps disconnecting every 10 minutes.",
  "session_id": "optional-uuid-for-multi-turn",
  "category": "VPN"
}

// Response (abridged)
{
  "session_id": "550e8400-...",
  "response": "⏳ IN PROGRESS — ...",
  "trace_id": "abc123...",
  "tool_trace": [{"tool": "search_knowledge_base", "phase": "finished", "duration_ms": 412.1}],
  "sources": [{"title": "VPN Troubleshooting Guide", "category": "VPN", "score": 0.87}]
}
```

---

## Guardrails & Security

- API keys live only in `.env`; never in prompts, source or logs.
- Service lookups are allow-listed; unknown names are blocked and audited.
- Ticket inputs are validated (priority enum, non-empty summary/category).
- KB search applies a low-confidence threshold — below it the tool instructs the model to clarify/escalate instead of guessing.
- Sensitive executions require a verified human approval record (see above); every decision point writes an `AuditLog` row (`approval_requested`, `approval_approved/rejected`, `sensitive_action_executed`, `security_blocked_*`).
- Structured JSON logs with per-request trace IDs; dev mode uses pretty console output.

---

## Running Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

Covers: config/API contracts, DB + repositories, RAG behaviour (mocked), deterministic + sticky routing conditions, guardrails/allow-lists, history idempotency, and the full approval lifecycle including REST decisions and replay protection. (48 tests)

---

## Project Structure

```
SupportPilot-AI/
├── config/
│   ├── __init__.py                    # Settings (Pydantic models)
│   └── settings.py                    # Re-export
│
├── core/                              # Central business logic & safeguards
│   ├── audit/                         # Structured audit logging
│   │   └── audit_logger.py
│   ├── guardrails/                    # Input + Output guardrails pipeline
│   │   ├── base.py                    # Abstract GuardrailBase class
│   │   ├── pipeline.py                # GuardrailPipeline orchestrator
│   │   ├── input/                     # Pre-execution validation
│   │   │   ├── contextual_compliance.py
│   │   │   ├── input_validation.py    # Schema, length, character sanity
│   │   │   ├── pii_detector.py        # SSN, email, phone, CC detection
│   │   │   ├── prompt_injection.py    # Injection & jailbreak detection
│   │   │   └── prompt_safety.py       # Toxicity & safety classifier
│   │   └── output/                    # Post-execution validation
│   │       ├── content_moderation.py  # Harmful output filter
│   │       ├── hallucination_check.py # Grounding & consistency check
│   │       ├── output_validation.py   # Schema & format verification
│   │       └── pii_leakage.py         # Outbound PII sanitization
│   ├── middleware/                    # Security & observability middleware
│   │   ├── auth.py                    # API key validation
│   │   ├── logging_middleware.py      # Request lifecycle & trace-ID logging
│   │   ├── pii_redaction.py           # Log sanitization
│   │   ├── rate_limiter.py            # Token-bucket rate limiting
│   │   └── secrets_filter.py          # API key & token masking in logs
│   ├── orchestration/                 # Multi-agent coordination layer
│   │   ├── router.py                  # Triage executor & sticky approval routing
│   │   ├── agents/                    # Specialized MAF agents
│   │   │   ├── tier1_agent.py         # Tier-1 IT Support agent
│   │   │   └── tier2_agent.py         # Tier-2 Escalation & approval agent
│   │   ├── prompts/                   # Isolated system prompts
│   │   │   ├── tier1_prompt.py
│   │   │   └── tier2_prompt.py
│   │   └── providers/                 # LLM & state providers
│   │       ├── groq_client.py         # Groq OpenAI-compatible client factory
│   │       └── history_provider.py    # Async SQLite conversation history
│   └── privacy/                       # PII redaction engine
│       ├── pii_patterns.py            # Regex patterns for sensitive data
│       ├── redactor.py                # Redaction & masking engine
│       └── retention.py               # Data lifecycle & retention
│
├── knowledge_base/                    # Curated IT articles (*.md with frontmatter)
├── static/                            # Web UI (index.html, styles.css)
│
├── src/
│   ├── api/                           # FastAPI application layer
│   │   ├── main.py                    # Entry point & lifespan management
│   │   ├── schemas.py                 # Pydantic request/response schemas
│   │   └── routes/                    # chat · tickets · sessions · services · approvals
│   ├── observability/                 # Tracing & telemetry
│   │   ├── logger.py                  # structlog configuration
│   │   ├── metrics.py                 # Prometheus latency & error metrics
│   │   ├── request_context.py         # Session & trace contextvars
│   │   ├── sampling.py                # Trace sampling policies
│   │   ├── tooltrace.py               # Tool execution performance collector
│   │   └── tracing.py                 # OpenTelemetry distributed tracing
│   ├── persistence/                   # Data layer
│   │   ├── database.py                # SQLAlchemy engine & session factory
│   │   ├── models.py                  # Ticket · AuditLog · SessionMessage · ApprovalRequest
│   │   └── repositories.py            # Repository pattern CRUD & dedup
│   ├── rag/                           # Production RAG pipeline
│   │   ├── chunker.py                 # Semantic chunking with overlap
│   │   ├── embedder.py                # MiniLM embedding pipeline
│   │   ├── ingestor.py                # Markdown vector ingestor
│   │   ├── reranker.py                # Cross-encoder similarity reranking
│   │   └── retriever.py               # Scored hybrid retrieval (+ category filter)
│   ├── services/                      # Business integrations
│   │   └── ad_directory.py            # Active Directory simulation
│   ├── tools/                         # Deterministic agent tools
│   │   ├── approval.py                # request_approval · execute_approved_action
│   │   ├── check_service_status.py    # Allow-listed service health checks
│   │   ├── create_ticket.py           # Validated IT ticketing
│   │   ├── get_ticket_status.py       # Ticket state queries
│   │   └── search_knowledge_base.py   # Grounded RAG retrieval tool
│   └── mcp_server.py                  # FastMCP stdio server (read-only AD tools)
│
└── tests/                             # Full test suite (56 unit & integration tests)
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Microsoft Agent Framework 1.14.0 (WorkflowBuilder, harness agents, MCP tool) |
| LLM | Groq `openai/gpt-oss-120b` via OpenAI-compatible **chat-completions** endpoint |
| API | FastAPI + uvicorn |
| Persistence | SQLAlchemy 2 + SQLite (PostgreSQL-ready) |
| RAG | ChromaDB + sentence-transformers MiniLM |
| MCP | official `mcp<2` SDK (stdio server) |
| Settings / Logging | pydantic-settings / structlog |
| Testing | pytest + pytest-asyncio + httpx |

### MAF/Groq compatibility notes

These integration quirks are handled in code — keep them in mind when upgrading:

- Use `OpenAIChatCompletionClient` (**not** `OpenAIChatClient`) — Groq has no Responses API.
- Harness flags required for Groq: `disable_web_search=True`, `disable_todo=True`, `disable_mode=True`.
- Custom `HistoryProvider` methods must be `async def` (MAF awaits them).
- Workflow routers must use `ctx.send_message(...)`; `ctx.yield_output()` ends the run.
- The MCP stdio server is spawned with `sys.executable` and self-registers the project root on `sys.path`.

---

## Docker

```bash
cp .env.example .env   # set GROQ_API_KEY
docker compose up --build
```

The SQLite DB is volume-mounted so tickets/sessions/approvals persist across restarts; the knowledge base is auto-ingested at first boot.
