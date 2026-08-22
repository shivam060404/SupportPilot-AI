# SupportPilot AI

> **AI-powered IT Support Agent** built with **Microsoft Agent Framework (MAF) 1.14.0**, Groq LLaMA, FastAPI, RAG, MCP, and a code-enforced human-approval gate.

```
Browser Chat UI (approvals panel, tool/source rendering)
      ↓
    FastAPI  ── REST: chat · tickets · sessions · services · approvals
      ↓
Microsoft Agent Framework WorkflowBuilder (deterministic routing)
      ↙                              ↘
Tier-1 IT Agent                  Tier-2 Escalation Agent
RAG · service status · tickets   MCP AD lookups + approval-gate tools
      ↘                              ↙
          Groq LLaMA 3.3-70B (OpenAI-compatible endpoint)
                     ↓
     SQLite (tickets · audit log · sessions · approvals)
     ChromaDB (knowledge-base vectors)
```

## Human-in-the-loop by design

Sensitive actions (e.g. `unlock_account`) are **never** reachable by the LLM directly:

1. The Tier-2 agent calls `request_approval` → a `PENDING` record is stored and audited.
2. A human approves/rejects via the UI panel or `POST /api/v1/approvals/{id}/approve|reject`.
3. Only `execute_approved_action` can run the capability — it independently verifies a matching `APPROVED` record in the database before touching the business service. Mismatched targets, replays (`ALREADY_EXECUTED`), rejections and unapproved attempts are all blocked and audit-logged.

The sensitive capability is deliberately **not** exposed on the MCP server; enforcement lives outside the LLM.

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
PYTHONPATH=. uvicorn src.api.main:app --reload --port 8000
```

On startup the app auto-ingests `knowledge_base/` into ChromaDB if the vector store is empty. To force a re-index after editing articles:

```bash
python -m src.rag.ingestor
```

### 5. Open the chat UI

Visit **http://localhost:8000**. Conversations survive page reloads (session restore) and server restarts (SQLite-backed history).

**Try the approval flow:** ask *"My AD account is locked, please unlock it"* → the Tier-2 agent investigates via MCP, files an approval request, and pauses. A red bell appears in the header — approve it, then tell the agent to continue.

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

Covers: config/API contracts, DB + repositories, RAG behaviour (mocked), deterministic routing conditions, guardrails/allow-lists, history idempotency, and the full approval lifecycle including REST decisions and replay protection.

---

## Project Structure

```
SupportPilot AI/
├── config/__init__.py             # Pydantic settings (all config here)
├── knowledge_base/*.md            # Approved IT articles (frontmatter metadata)
├── static/index.html|styles.css   # Chat UI + approvals panel
├── src/
│   ├── agents/
│   │   ├── supervisor_agent.py    # MAF workflow: triage → Tier-1 / Tier-2
│   │   ├── escalation_agent.py    # Tier-2: MCP lookups + approval-gate tools
│   │   ├── prompts.py             # Tier-1 system prompt
│   │   ├── prompts_approval.py    # Tier-2 system prompt (approval protocol)
│   │   └── sqlite_history_provider.py
│   ├── api/
│   │   ├── main.py                # FastAPI entry point (lifespan init)
│   │   ├── schemas.py             # All request/response models
│   │   ├── middleware.py          # Trace-ID + request logging
│   │   └── routes/                # chat · tickets · sessions · services · approvals
│   ├── observability/
│   │   ├── logger.py              # structlog configuration
│   │   ├── request_context.py     # session/trace contextvars
│   │   └── tooltrace.py           # per-request tool-call trace collector
│   ├── persistence/
│   │   ├── models.py              # Ticket · AuditLog · SessionMessage · ApprovalRequest
│   │   ├── repositories.py        # CRUD + validation + audit wiring
│   │   └── database.py
│   ├── rag/
│   │   ├── ingestor.py            # markdown → chunks → embeddings
│   │   └── retriever.py           # scored retrieval (+ category filter)
│   ├── services/ad_directory.py   # mock AD business logic (shared)
│   ├── tools/
│   │   ├── search_knowledge_base.py · check_service_status.py
│   │   ├── create_ticket.py · get_ticket_status.py
│   │   └── approval.py            # request_approval · execute_approved_action
│   └── mcp_server.py              # stdio MCP server (read-only AD lookups)
└── tests/                         # phase + approvals + guardrails suites
```

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Agent Framework | Microsoft Agent Framework 1.14.0 |
| LLM | Groq LLaMA 3.3-70B (OpenAI-compatible endpoint) |
| API | FastAPI + uvicorn |
| Persistence | SQLAlchemy 2 + SQLite (PostgreSQL-ready) |
| RAG | ChromaDB + sentence-transformers MiniLM |
| MCP | official `mcp` SDK (stdio server) |
| Settings / Logging | pydantic-settings / structlog |
| Testing | pytest + pytest-asyncio + httpx |

---

## Docker

```bash
cp .env.example .env   # set GROQ_API_KEY
docker compose up --build
```

The SQLite DB is volume-mounted so tickets/sessions/approvals persist across restarts; the knowledge base is auto-ingested at first boot.
