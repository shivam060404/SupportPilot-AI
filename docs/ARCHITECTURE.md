# SupportPilot AI — System Architecture

## 1. Architecture goals

SupportPilot is organized around clear runtime and ownership boundaries:

- The **frontend** is a thin client for user interaction.
- The **API** owns transport, validation, lifecycle, and response contracts.
- The **AI subsystem** owns routing, agents, prompts, retrieval, tools,
  guardrails, memory, and evaluation.
- **Persistence** owns PostgreSQL access and transactional state.
- **Integrations** isolate external providers.
- **Observability** is cross-cutting and does not own business decisions.

The architecture favors explicit composition over a large framework abstraction.
Every folder exists because it owns a concrete responsibility.

## 2. Context and deployment topology

```text
                                  ┌────────────────────────────┐
                                  │        Browser user        │
                                  └─────────────┬──────────────┘
                                                │ HTTPS / JSON
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ frontend/                                                                    │
│ Next.js App Router                                                            │
│ - categories, conversation UI, loading/error states                           │
│ - calls backend API; contains no LLM, persistence, or authorization logic     │
└────────────────────────────────────┬─────────────────────────────────────────┘
                                     │ REST
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ backend/app/api/                                                             │
│ FastAPI application                                                          │
│ - routes, Pydantic schemas, CORS, middleware, lifecycle, health, metrics      │
└───────────────┬──────────────────────┬──────────────────────┬────────────────┘
                │                      │                      │
                ▼                      ▼                      ▼
┌──────────────────────┐  ┌───────────────────────┐  ┌────────────────────────┐
│ backend/app/ai/      │  │ backend/app/persistence│  │ backend/app/observability│
│ agents, RAG, tools,  │  │ SQLAlchemy + Alembic  │  │ logs, metrics, traces,  │
│ prompts, guardrails  │  │                       │  │ request/tool context     │
└───────┬──────────────┘  └───────────┬───────────┘  └────────────────────────┘
        │                             │
        ▼                             ▼
┌──────────────────────┐  ┌────────────────────────┐
│ Groq / Agent Framework│  │ PostgreSQL              │
│ Chroma vector store  │  │ tickets, approvals,     │
│ MCP directory server │  │ audit, session messages │
└──────────────────────┘  └────────────────────────┘
```

Docker Compose runs `postgres`, `backend`, and `frontend`. PostgreSQL has a
healthcheck; the backend depends on PostgreSQL readiness. The frontend talks to
the backend through `NEXT_PUBLIC_API_URL`.

## 3. Dependency direction

```text
frontend
   │ HTTP contract only
   ▼
api ───────────────► services / ai orchestration
                       │       │
                       │       ├── integrations
                       │       ├── persistence
                       │       └── observability
                       │
                       ├── agents
                       ├── prompts
                       ├── rag
                       ├── tools
                       ├── memory
                       └── guardrails
```

Rules:

1. API modules may import schemas, services, AI entry points, and cross-cutting
   middleware, but must not contain large model or database implementations.
2. AI modules may request persistence or integration capabilities through
   existing repositories/adapters; they must not reach into frontend code.
3. Persistence does not import API routes or prompt/agent implementations.
4. Integrations wrap provider SDKs so provider-specific details do not leak
   through every feature.
5. Observability may be called by all layers but does not decide business
   outcomes.
6. The frontend depends on HTTP response shapes, not Python module paths.

## 4. Request lifecycle

### 4.1 Chat request

```text
POST /api/v1/chat
        │
        ▼
Pydantic request validation
        │
        ▼
trace_id + session_id context
        │
        ▼
input guardrails
        │ blocked ───────────────► safe blocked response
        ▼
deterministic triage
        │
        ├── normal support ──────► Knowledgeable IT Support Agent
        └── sensitive access ────► Privileged Access Escalation Agent
                                      │
                                      ├── read-only AD MCP lookup
                                      ├── request human approval
                                      └── execute only matching approval
        │
        ▼
tools / RAG / history / LLM
        │
        ▼
output guardrails and grounding metadata
        │
        ▼
ChatResponse: answer, session, trace, sources, tool trace, safety metadata
```

### 4.2 Session continuity

The client sends the `session_id` returned by a previous response. The
PostgreSQL-backed history provider serializes and reloads conversation messages.
The repository layer handles persistence; the agent layer is responsible for
using the history provider when creating the Agent Framework session.

## 5. AI subsystem

### 5.1 Agents and routing

`backend/app/ai/router.py` performs deterministic pre-triage using sensitive
keywords and unresolved approval state. This avoids asking the LLM to decide
whether a request should enter a privileged workflow.

- **Knowledgeable IT Support Agent**
  - Grounded troubleshooting for common IT issues.
  - Uses knowledge search, service status, ticket creation, and ticket lookup.
  - Uses the standard IT support prompt.

- **Privileged Access Escalation Agent**
  - Handles account lockouts, directory lookups, manager escalation, and
    sensitive access requests.
  - Uses read-only MCP directory tools plus local approval-gate tools.
  - Cannot directly unlock accounts or bypass human approval.

Agent names communicate responsibility rather than implementation tier.

### 5.2 Guardrails

`backend/app/ai/guardrails/` owns the pre/post model safety pipeline.

Input checks include:

- input validation,
- prompt-injection detection,
- prompt-safety checks,
- PII detection/redaction,
- contextual compliance.

Output checks include:

- output validation,
- PII leakage detection,
- content moderation,
- hallucination/grounding checks.

Guardrails can block unsafe input, sanitize content, attach metadata, or replace
an unsafe output. The API exposes the resulting safety state without exposing
internal secrets or raw provider errors.

### 5.3 Tools and approvals

Tools are callable capabilities, not authorization policy. The approval tool
flow is enforced outside the model:

```text
request_approval
      │
      ▼
PENDING record in PostgreSQL
      │ human decision
      ├── REJECTED ─────► execution denied
      └── APPROVED
             │ exact action + target checked
             ▼
execute_approved_action
             │
             ▼
EXECUTED record + audit event
```

An approval is scoped to its session, action, and target. Missing, rejected,
expired, duplicated, or mismatched approval records must fail closed.

### 5.4 RAG and vector storage

The source of truth is `data/knowledge_base/`. The RAG pipeline parses source
Markdown, applies metadata defaults, chunks content with overlap, embeds
chunks, and stores them in the Chroma `support_kb` collection.

Chroma is retained instead of moving vectors into PostgreSQL merely for
architectural appearance. PostgreSQL is the transactional system of record;
Chroma is the document retrieval index. A pgvector migration should be
considered only when transactional filtering, index scale, or operational
requirements justify the added coupling.

Generated vectors belong under ignored `data/runtime/`. They are reproducible
from the Markdown source and should not be committed.

## 6. Persistence architecture

`backend/app/persistence/` contains:

- `database.py`: PostgreSQL SQLAlchemy engine, sessions, and readiness check.
- `models.py`: ORM models for tickets, audit logs, session messages, and
  approval requests.
- `repositories.py`: explicit CRUD and workflow persistence operations.

Alembic migrations under `backend/alembic/` are the schema source of truth.
Startup checks connectivity but does not call `Base.metadata.create_all()` or
silently mutate a production schema.

Current transactional tables:

| Table | Responsibility |
| --- | --- |
| `tickets` | IT support ticket records |
| `approval_requests` | Human approval state machine |
| `audit_logs` | Security and operational audit events |
| `session_messages` | Durable conversation transcript payloads |

Database credentials and connection URLs are environment-provided. Local
Compose exposes PostgreSQL for pgAdmin or another PostgreSQL GUI.

## 7. Integration boundaries

### LLM provider

`backend/app/integrations/groq_client.py` creates the OpenAI-compatible Groq
client. Agents receive the configured client; route handlers never construct
provider SDK clients.

### MCP

`backend/app/mcp/server.py` is a separate stdio MCP server for read-only
Active Directory lookups. The escalation agent launches it with the same Python
interpreter as the backend. Privileged local tools remain outside MCP so the
approval gate stays in the application-controlled persistence path.

### History

`backend/app/integrations/history_provider.py` adapts Agent Framework history
operations to PostgreSQL-backed session repositories. This keeps framework
message serialization separate from ORM details.

## 8. Security and privacy

- Secrets are loaded from environment variables and excluded from Git.
- Optional API-key middleware protects non-public endpoints when enabled.
- CORS is configured explicitly through `CORS_ORIGINS`.
- PII detection and redaction run in the guardrail/privacy layers.
- Audit events record approval and sensitive-action decisions.
- Model output is never treated as authorization.
- MCP exposes only the directory capabilities required by the escalation flow.
- Database access uses PostgreSQL credentials supplied at runtime.
- Errors should be logged with trace/session context without leaking secrets.

## 9. Observability

The observability layer provides:

- structured application logging,
- request and trace context,
- tool-call traces,
- RAG source artifacts,
- metrics at `/metrics`,
- tracing/sampling hooks.

The chat response carries a trace identifier and explainability metadata so an
operator can connect user-visible behavior to backend activity. Observability
must not change authorization or safety outcomes.

## 10. Failure and readiness behavior

- PostgreSQL unavailability is a readiness/startup failure and must be visible.
- Missing `GROQ_API_KEY` leaves the service importable but prevents live agent
  execution; deployment configuration should treat the key as required.
- Chroma ingestion failures are logged and may leave the API available without
  grounded retrieval; this state must remain observable.
- Input guardrail blocks return a structured safe response, not a model call.
- Output guardrail failures return a sanitized/fallback response rather than
  exposing unsafe content.
- Approval or target mismatches fail closed.

## 11. Testing strategy

```text
backend/tests/       backend-local tests
tests/evaluation/    guardrails, RAG, and AI behavior boundaries
tests/integration/   API, database, approvals, tools, and workflow routing
tests/e2e/           browser-to-service journeys
tests/load/          latency, concurrency, and throughput validation
```

Required review gates:

```bash
pytest
cd frontend && npm run typecheck && npm run build
docker compose config
docker compose -f docker-compose.prod.yml config
alembic upgrade head
```

The most important regression boundaries are deterministic routing, approval
enforcement, guardrail behavior, persistence lifecycle, RAG source attribution,
and frontend/backend contract compatibility.

## 12. Change strategy

When adding a feature:

1. Identify its owning boundary.
2. Add or update the backend contract/schema.
3. Implement the use case in a service, AI component, integration, or
   repository—not in the route handler.
4. Add guardrail/audit behavior if the feature is sensitive.
5. Add targeted tests in the correct test boundary.
6. Update Alembic when persistence changes.
7. Update frontend types and API usage without duplicating backend logic.
8. Update this document when ownership or dependency direction changes.

This keeps the repository navigable for a new engineer and makes architectural
trade-offs explainable during technical review.
