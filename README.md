# SupportPilot AI

SupportPilot AI is an AI-assisted IT support platform for employee
troubleshooting, knowledge retrieval, ticket creation, service-status checks,
and controlled escalation of privileged account requests.

The repository is deliberately split into two deployable applications:

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, ChromaDB, and
  the Microsoft Agent Framework.
- **Frontend:** Next.js and React. It owns presentation and browser interaction
  only; it does not contain AI, authorization, persistence, or business rules.

The design goal is a system that is straightforward to review, operate, test,
and extend without creating duplicate implementations or unsafe model-driven
authorization.

## What the system does

1. An employee selects an issue category and submits a message in the Next.js
   client.
2. The frontend sends JSON to `POST /api/v1/chat`.
3. FastAPI validates the request, creates or resumes a session, and establishes
   trace/request context.
4. Input guardrails validate content, detect prompt injection, detect PII, and
   enforce safety and scope rules.
5. Deterministic triage routes normal support questions to the IT support agent
   and sensitive account/access questions to the privileged-access escalation
   agent.
6. The agent can retrieve approved knowledge, check service status, create or
   inspect tickets, or begin a human approval workflow.
7. Output guardrails validate and sanitize the generated response.
8. The API returns the answer, session identifier, trace identifier, tool trace,
   grounding metadata, and knowledge sources where available.

Model output never grants privileged access. Sensitive actions require a
persisted approval record and an explicit execution-side check.

## Repository structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/                 FastAPI app, routes, schemas, lifecycle
│   │   ├── ai/
│   │   │   ├── agents/          Support and privileged-access agents
│   │   │   ├── evaluation/      AI evaluation boundary
│   │   │   ├── guardrails/      Input/output safety pipeline
│   │   │   ├── memory/          AI memory boundary
│   │   │   ├── prompts/         Versioned agent instructions
│   │   │   ├── rag/             Chunking, embedding, ingestion, retrieval
│   │   │   └── tools/           Ticket, service, approval, and KB tools
│   │   ├── core/
│   │   │   ├── audit/           Audit logging concerns
│   │   │   ├── config/          Environment-backed settings
│   │   │   ├── middleware/      Auth, logging, rate limiting, redaction
│   │   │   └── privacy/        PII patterns, redaction, retention
│   │   ├── integrations/        Groq client and PostgreSQL history adapter
│   │   ├── mcp/                 Active Directory MCP server
│   │   ├── observability/       Logs, metrics, tracing, tool traces
│   │   ├── persistence/         SQLAlchemy engine, models, repositories
│   │   └── services/             External/domain service adapters
│   ├── alembic/                 PostgreSQL migrations
│   ├── tests/                   Backend-only test boundary
│   ├── Dockerfile
│   ├── requirements.txt
│   └── requirements-dev.txt
├── data/
│   ├── knowledge_base/          Markdown source articles
│   └── runtime/                 Ignored generated Chroma data
├── frontend/
│   ├── src/app/                 Next.js App Router pages and styles
│   ├── src/components/          Reusable UI components
│   ├── src/features/            Feature-specific UI modules
│   ├── src/hooks/               React hooks
│   ├── src/lib/                 Frontend utilities
│   ├── src/services/            Backend API clients
│   ├── src/types/               Frontend contract types
│   ├── public/                  Browser assets
│   └── Dockerfile
├── tests/
│   ├── integration/              API, persistence, workflow, approval tests
│   ├── e2e/                     Browser/system test boundary
│   ├── evaluation/              Guardrail and RAG quality tests
│   └── load/                    Load/system test boundary
├── docs/                        Operational and supporting documentation
├── ARCHITECTURE.md              Detailed system architecture
├── docker-compose.yml            Local multi-service environment
├── docker-compose.prod.yml       Production-oriented Compose topology
├── alembic.ini                  Migration entry point
├── .env.example                 Safe configuration template
└── Makefile                     Common developer commands
```

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer and npm
- Docker Desktop or Docker Engine with Compose
- A Groq API key for live agent execution

## Configuration

Copy the committed template and provide local values:

```bash
cp .env.example .env
```

Important variables:

| Variable | Purpose |
| --- | --- |
| `GROQ_API_KEY` | LLM provider credential; required for live chat |
| `GROQ_MODEL` | Groq/OpenAI-compatible model identifier |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection URL |
| `CORS_ORIGINS` | Comma-separated browser origins |
| `CHROMA_PERSIST_DIR` | Runtime Chroma persistence directory |
| `EMBEDDING_MODEL` | Sentence-transformer embedding model |
| `NEXT_PUBLIC_API_URL` | Browser-visible backend base URL |
| `API_KEY_REQUIRED` / `API_KEY` | Optional API-key middleware controls |

Never commit `.env`, provider credentials, database passwords, generated
Chroma data, or local database files.

## Run locally with Docker

The recommended path starts PostgreSQL, the backend, and the frontend together:

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY
docker compose up --build
```

Endpoints:

- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- OpenAPI UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Metrics: <http://localhost:8000/metrics>
- Health: <http://localhost:8000/api/v1/health>
- PostgreSQL: `localhost:5432`

Stop services with:

```bash
docker compose down
```

The production-oriented topology is:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

For production, use externally managed secrets and persistent PostgreSQL
storage. Do not use the example credentials outside local development.

## Run without Docker

Start PostgreSQL separately, set `DATABASE_URL`, then create a Python
environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn backend.app.api.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

## Database and migrations

PostgreSQL is the application system of record for tickets, approvals, audit
logs, and conversation messages. SQLAlchemy provides the engine, sessions,
models, and repositories. Alembic is the schema authority.

Apply migrations:

```bash
alembic upgrade head
```

Create a migration after a model change:

```bash
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

Application startup performs a connection/readiness check. It does not silently
create production tables; schema changes must be explicit and reviewable.

Chroma remains separate from PostgreSQL because the current workload is a
small, document-oriented knowledge base with an existing Chroma retrieval
pipeline. Generated vector data belongs in ignored runtime storage, while
Markdown articles under `data/knowledge_base/` remain the source of truth.

## Knowledge base ingestion

Knowledge articles are Markdown files with optional metadata/frontmatter. The
ingestion pipeline:

1. Reads source articles from `data/knowledge_base/`.
2. Validates/defaults document metadata.
3. Splits content into overlapping semantic chunks.
4. Generates embeddings.
5. Rebuilds the `support_kb` Chroma collection.
6. Stores runtime vector data under `data/runtime/chroma/`.

The API also checks whether retrieval is available during startup and attempts
non-fatal knowledge-base initialization. A retrieval failure must not be
confused with an authorization decision or a database failure.

## Testing and validation

Run backend and AI tests:

```bash
pytest
```

Run frontend checks:

```bash
cd frontend
npm run typecheck
npm run build
```

Validate infrastructure and migrations:

```bash
docker compose config
docker compose -f docker-compose.prod.yml config
alembic upgrade head
```

Test responsibilities:

- `tests/evaluation/`: guardrails, RAG behavior, and AI quality boundaries.
- `tests/integration/`: API contracts, persistence, approvals, and workflow
  routing.
- `tests/e2e/`: browser-to-backend flows.
- `tests/load/`: concurrency, latency, and throughput scenarios.
- `backend/tests/`: backend-local tests that should not require browser tooling.

## Design principles

- Keep API handlers thin; business and AI orchestration belongs below the API.
- Keep one source of truth for each capability.
- Keep frontend code independent from Python internals.
- Make privileged operations deterministic and approval-gated.
- Prefer explicit failures and observable errors over silent fallbacks.
- Keep configuration environment-based and secrets out of source control.
- Make migrations, prompts, guardrails, and evaluation boundaries reviewable.

For the full dependency model and request lifecycle, read
[`ARCHITECTURE.md`](ARCHITECTURE.md).
