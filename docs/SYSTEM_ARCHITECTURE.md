# SupportPilot AI — System Architecture Design

> Version 1.0 · Microsoft Agent Framework (MAF) 1.14.0 · Groq `openai/gpt-oss-120b` · FastAPI · SQLite · ChromaDB · MCP

---

## 1. System Overview

SupportPilot AI is an IT-support chat system where employees describe problems in natural language and a **multi-agent LLM workflow** produces *grounded* troubleshooting answers, performs *controlled* actions (tickets, service lookups), and routes *sensitive* operations through a **code-enforced human-approval gate**.

Design principle: **the LLM decides *what* to do; deterministic code decides *what is allowed*.**

```
                        ┌────────────────────────────────────────────────┐
                        │                  EMPLOYEE / IT STAFF           │
                        └───────────┬───────────────────────▲────────────┘
                                    │ chat / approvals UI   │ replies + approval cards
                            ┌───────▼────────┐              │
                            │  Browser UI    │ static/index.html + styles.css
                            └───────┬────────┘              │
                                    │ HTTPS JSON            │
┌───────────────────────────────────▼───────────────────────────────────────────────┐
│                             FASTAPI APPLICATION LAYER                              │
│   LoggingMiddleware ── routes (chat · tickets · sessions · services · approvals)   │
└───────────────────────────────────┬───────────────────────────────────────────────┘
                                    │ agent.chat(message, session_id, trace_id)
┌───────────────────────────────────▼───────────────────────────────────────────────┐
│                          MAF WORKFLOW (supervisor_agent)                           │
│      TriageExecutor ──conditional edges──▶ Tier-1 Agent │ Tier-2 Agent             │
└──────────────┬──────────────────────────────────┬─────────────────────────────────┘
               │ tools                            │ MCP stdio + approval-gate tools
┌──────────────▼──────────────┐    ┌──────────────▼─────────────────────────────────┐
│ Deterministic tool layer    │    │ Business services (ad_directory)                │
│ RAG search · status · tickets│   │ reachable ONLY via verified approval records    │
└──────────────┬──────────────┘    └──────────────┬─────────────────────────────────┘
               │                                   │
┌──────────────▼───────────────────────────────────▼─────────────────────────────────┐
│        PERSISTENCE: SQLite (Ticket · AuditLog · SessionMessage · ApprovalRequest)  │
│        VECTOR STORE: ChromaDB (knowledge_base/*.md → MiniLM embeddings)            │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities

| Component | File(s) | Responsibility |
|---|---|---|
| **Web UI** | `static/index.html`, `styles.css` | Chat interface, approvals bell/panel, renders tool-trace chips + RAG source citations, restores sessions |
| **API layer** | `src/api/main.py`, `src/api/routes/*` | HTTP surface, validation via Pydantic schemas, trace-ID lifecycle, error mapping |
| **Middleware** | `core/middleware/logging_middleware.py` | Per-request trace ID (`x-trace-id`), structured access logs, contextvar binding |
| **Supervisor / workflow** | `core/orchestration/router.py` | Builds MAF workflow, conditional routing (incl. sticky approval routing) |
| **Tier-1 agent** | `core/orchestration/agents/tier1_agent.py`, `core/orchestration/prompts/tier1_prompt.py` | Grounded troubleshooting; tools: KB search, service status, ticket create/get |
| **Tier-2 agent** | `core/orchestration/agents/tier2_agent.py`, `core/orchestration/prompts/tier2_prompt.py` | Lockouts/AD matters; MCP read-only lookups + `request_approval` / `execute_approved_action` |
| **History provider** | `core/orchestration/providers/history_provider.py` | Async MAF `HistoryProvider`; idempotent message persistence |
| **Tools** | `src/tools/*` | `@af.tool` functions wrapped by trace decorator; all guardrails applied here |
| **Guardrails** | `core/guardrails/*` | PII redaction, Prompt injection detection, Output hallucination/policy checks |
| **Audit Logger** | `core/audit/audit_logger.py` | Structured JSON auditing for sensitive business events |
| **Approval gate** | `src/tools/approval.py` | `request_approval`, `execute_approved_action` — DB-verified human-in-the-loop |
| **Business services** | `src/services/ad_directory.py` | Mock AD logic shared by MCP server and guarded executor |
| **MCP server** | `src/mcp_server.py` | Stdio FastMCP server exposing **read-only** AD lookups only |
| **RAG** | `src/rag/ingestor.py`, `retriever.py` | Markdown → chunking → MiniLM embeddings → ChromaDB; scored retrieval w/ category filter |
| **Persistence** | `src/persistence/*` | SQLAlchemy models + repositories (validation, auditing, dedup) |
| **Observability** | `src/observability/*` | structlog config, request contextvars, per-request tool-call trace collector |

---

## 3. Flow 1 — Generic Chat Request Lifecycle

Every conversation turn follows this pipeline:

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser UI
    participant MW as LoggingMiddleware
    participant CH as POST /api/v1/chat
    participant AG as SupportAgent.chat()
    participant WF as MAF Workflow
    participant TL as Tools (deterministic)

    U->>MW: POST {message, session_id?, category?}
    MW->>MW: generate/propagate trace_id → contextvars
    MW->>CH: call_next(request)
    CH->>AG: chat(message+category hint, session_id, trace_id)
    AG->>AG: set_request_context(session_id, trace_id)<br/>persist user turn → SQLite
    AG->>WF: workflow_agent.run(msgs, session)
    WF->>WF: TriageExecutor → conditional edges<br/>(keywords OR open approval loop)
    WF->>TL: selected agent runs tool-calling loop<br/>(max 10 iters T1 / 8 iters T2)
    TL-->>WF: JSON results (validated, audited, traced)
    WF-->>AG: final AgentResponse.text
    AG->>AG: persist assistant turn → SQLite
    AG-->>CH: {session_id, response, trace_id}
    CH->>CH: collect tool_trace + RAG sources (contextvars)
    CH-->>U: 200 ChatResponse (reply + tool_trace + sources)
    Note over U: renders badges, sources 📚, tool chips 🔧,<br/>polls pending approvals every 5 s
```

**Trace-ID rule:** one ID per request — generated by middleware, reused by route, agent, logs and response header. Never generated twice.

---

## 4. Flow 2 — Tier-1 Grounded Troubleshooting (RAG)

```mermaid
flowchart TD
    A[User message e.g. 'VPN keeps dropping'] --> B{Pre-triage keywords?<br/>locked/unlock/manager...}
    B -- no match --> C[Tier-1 IT Agent]
    B -- match --> X[(Flow 3: Tier-2)]
    C --> D[search_knowledge_base query, category?]
    D --> E{ChromaDB hits ≥<br/>LOW_CONFIDENCE_THRESHOLD 0.30?}
    E -- no --> F[Return no_trusted_results:<br/>'Do NOT guess' instruction]
    F --> G[Agent asks clarifying question<br/>or creates ticket]
    E -- yes --> H[Agent grounds answer in chunks,<br/>cites article titles]
    H --> I[record_artifact: sources + scores<br/>→ returned as response.sources]
    I --> J[/UI shows 📚 Grounded-in box/]
```

**Grounding contract:** the KB tool result carries an explicit instruction *"Ground your answer ONLY in these chunks and cite the source titles."* Below-threshold results are dropped server-side before the model ever sees them.

---

## 5. Flow 3 — Tier-2 Escalation & Human Approval (core security flow)

```mermaid
sequenceDiagram
    autonumber
    participant U as Employee
    participant API as FastAPI
    participant W as Workflow (sticky router)
    participant T2 as Tier-2 Agent (LLM)
    participant MCP as MCP AD Server (stdio)
    participant AR as ApprovalRepository (SQLite)
    participant S as Staff/Employee (human)

    U->>API: "My AD account x@co.com is locked"
    API->>W: run
    Note over W: keyword 'locked' matches → Tier-2
    W->>T2: AgentExecutorRequest
    T2->>MCP: ad_check_account_status(email)
    MCP-->>T2: "LOCKED due to failed logins"
    T2->>AR: request_approval(unlock_account, email) ①
    AR-->>T2: {approval_id, status: PENDING}  (audited)
    T2-->>U: "⏳ AWAITING APPROVAL — approve in UI"

    rect rgb(235, 245, 255)
        Note over U,S: Human decision — LLM cannot self-approve
        S->>API: POST /approvals/{id}/approve
        API->>AR: decide(id, APPROVED) ② (audited)
    end

    U->>API: "it's approved, go ahead"
    API->>W: run
    Note over W: STICKY ROUTING: open approval loop<br/>→ stays with Tier-2 (keywords not required)
    W->>T2: follow-up turn
    T2->>AR: execute_approved_action(action, target, approval_id) ③
    AR->>AR: GUARD: record exists? APPROVED? action+target match? not already EXECUTED?
    alt guard passes
        AR->>AR: ad_directory.unlock_account(target)
        AR->>AR: mark EXECUTED + audit sensitive_action_executed ④
        T2-->>U: "✅ RESOLVED — account unlocked"
    else any check fails
        AR-->>T2: DENIED / PENDING / REJECTED / ALREADY_EXECUTED
        Note over AR: audit security_blocked_sensitive_execution
    end
```

### Approval state machine

```mermaid
stateDiagram-v2
    [*] --> PENDING : request_approval()  [LLM may call]
    PENDING --> APPROVED : human decide() via REST/UI
    PENDING --> REJECTED : human decide() via REST/UI
    APPROVED --> EXECUTED : execute_approved_action()<br/>guard verified
    EXECUTED --> [*]
    REJECTED --> [*] : retry forbidden
    note right of PENDING
        execute_approved_action on PENDING
        returns PENDING (nothing runs)
    end note
    note right of EXECUTED
        replay attempt returns
        ALREADY_EXECUTED
    end note
```

**Enforcement layers for `unlock_account`:**

1. Not registered as an MCP tool at all (read-only lookups only).
2. Only reachable via `execute_approved_action`, which re-verifies the DB record independently of anything the LLM claims.
3. Target/action must byte-match the approved record.
4. Every branch (pass or block) writes an `AuditLog` row.

---

## 6. Routing & Triage Logic

```mermaid
flowchart TD
    M[Latest user message] --> K{Contains escalation keyword?<br/>locked · unlock · manager · escalate ·<br/>active directory · admin rights ...}
    K -- yes --> T2[Tier-2 Escalation Agent]
    K -- no --> S{Session has open approval loop?<br/>status ∈ PENDING,APPROVED}
    S -- yes --> T2
    S -- no --> T1[Tier-1 Support Agent]

    style T2 fill:#fee2e2,stroke:#ef4444
    style T1 fill:#dcfce7,stroke:#22c55e
```

- Implemented as MAF conditional edges on one pass-through `TriageExecutor`.
- Both conditions are pure functions of (payload, session context) → fully unit-testable without an LLM.
- Bare *password reset* questions stay Tier-1 (KB covers them); lockouts/unlocks/AD go Tier-2.

---

## 7. Data Model

```
┌──────────────────┐     ┌────────────────────┐     ┌─────────────────────────┐
│ Ticket           │     │ ApprovalRequest    │     │ AuditLog                │
├──────────────────┤     ├────────────────────┤     ├─────────────────────────┤
│ id PK uuid       │     │ id PK uuid         │     │ id PK uuid              │
│ status OPEN..    │     │ session_id idx     │◄──┐ │ session_id idx          │
│ category idx     │     │ action idx         │   │ │ action idx              │
│ priority enum    │     │ target             │   │ │ details JSON            │
│ summary TEXT     │     │ rationale          │   │ │ created_at              │
│ created_at       │     │ status PENDING →   │   │ └─────────────────────────┘
│ updated_at       │     │   APPROVED/REJECTED│   │
└──────────────────┘     │ requested_at       │   │  ┌──────────────────────┐
                         │ decided_at         │   │  │ SessionMessage       │
                         │ executed_at        │   │  ├──────────────────────┤
                         └────────────────────┘   │  │ id PK uuid           │
                                                  └──│ session_id idx       │
                             referenced by             │ message_json TEXT    │
                             tools via contextvars     │ created_at (ordered) │
                                                       └──────────────────────┘
```

Key behaviours:
- **Transcript writes are idempotent**: exact-JSON payloads already stored are skipped, so framework retries can never duplicate history (`SessionRepository.save_messages`).
- Repositories return **detached copies** of ORM objects (safe outside session scope).
- Auditing failures never break the main flow (`log_action` swallows + logs).

---

## 8. Tool Registry & Guardrail Matrix

| Tool | Layer | Inputs (typed) | Guardrail | Side effects |
|---|---|---|---|---|
| `search_knowledge_base` | Tier-1 | `query`, `category?` | Read-only ChromaDB; low-confidence threshold drops weak chunks | artifact: sources+scores |
| `check_service_status` | Tier-1 | `service_name` | **Allow-list** (`SERVICE_ALLOWLIST`); unknown → blocked + audited | none |
| `create_ticket` | Tier-1 | `summary`, `category`, `priority∈{LOW,MEDIUM,HIGH,CRITICAL}` | Repo-level validation (raises → JSON error) | INSERT ticket + audit |
| `get_ticket_status` | Tier-1 | `ticket_id` | Read-only | none |
| `request_approval` | Tier-2 | `action`, `target`, `rationale` | Action must exist in `SENSITIVE_ACTIONS` | INSERT approval + audit |
| `execute_approved_action` | Tier-2 | `action`, `target`, `approval_id` | **DB guard**: APPROVED + matching + not-executed | runs business service + audits both ways |
| MCP `ad_check_account_status` / `ad_get_manager_info` | Tier-2 (stdio subprocess) | `email` | Read-only; spawned with `sys.executable`, self-registers `sys.path` | none |

All local tools are additionally wrapped by `@traced_tool` → per-call `{tool, args(redacted), phase, duration_ms, ok}` events collected into a contextvar and surfaced in the chat response.

---

## 9. Observability Model

```
trace propagation (one ID end-to-end):

x-trace-id header ──▶ middleware binds contextvars ──▶ chat route reuses ──▶ agent logs
                                                                        └─▶ response.trace_id
session_id ──▶ request contextvars ──▶ tools/guards read identity from code, NEVER from LLM

three log/event streams:
1. structlog app logs      : dev = pretty console · prod = JSON; includes http_request timings
2. tool trace (per request): returned IN the ChatResponse → rendered as 🔧 chips in UI
3. AuditLog table (durable): ticket_created · approval_requested/approved/rejected ·
                             sensitive_action_executed · security_blocked_*
```

RAG retrievals log hit counts + top score (`kb_retrieval`, `kb_tool_hit`).

---

## 10. Security Model — Trust Boundaries

```
┌────────────────────────── TRUSTED (deterministic code) ──────────────────────────┐
│  allow-lists · input validation · approval verification · business services ·    │
│  audit writes · session identity (contextvars)                                   │
└──────────────────────────────▲───────────────────────────────────────────────────┘
                              │  narrow, typed interfaces (@af.tool JSON contracts,
                              │  REST endpoints) — outputs validated, inputs sanitized
┌──────────────────────────────┴───────────────────────────────────────────────────┐
│  UNTRUSTED / PROBABILISTIC: LLM outputs · free-text user input · retrieved text  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Rules enforced:
1. Identity (session_id/trace_id) enters tools via **contextvars**, never via LLM-supplied arguments.
2. No arbitrary SQL/shell/network reachability from any tool; service lookups allow-listed.
3. Secrets live only in `.env` (git-ignored); never logged (tool args redacted).
4. Sensitive capability unreachable except through the verified approval gate.
5. Low-confidence RAG instructs clarification/escalation instead of guessing.

---

## 11. Deployment Topology

**Local:** single uvicorn process; MCP server spawned lazily by MAF as a child process on first Tier-2 use.

```
uvicorn src.api.main:app :8000
 ├── lifespan: init_db() → auto-ingest ChromaDB if empty → build SupportAgent once
 ├── child: python src/mcp_server.py   (stdio, spawned on demand)
 └── files: supportpilot.db · data/chroma/* · agent-file-memory/ (framework cache)
```

**Docker:** `python:3.11-slim`; DB volume-mounted (`./supportpilot.db:/app/supportpilot.db`); KB auto-ingests at first boot.

Startup failure modes are non-fatal by design:
- Missing `GROQ_API_KEY` → boots fine; `/chat` returns explicit config error; all other endpoints work.
- Empty/failed KB ingest → chat still works (ungrounded), warning logged.

---

## 12. MAF 1.14 × Groq Compatibility Constraints

Handled in code; must be preserved across upgrades:

| Constraint | Where handled |
|---|---|
| Use `OpenAIChatCompletionClient`, not `OpenAIChatClient` (no Responses API on Groq) | `core/orchestration/providers/groq_client.py` |
| Harness flags: `disable_web_search=True`, `disable_todo=True`, `disable_mode=True` (Groq rejects injected params/tool schemas) | both agents |
| Custom `HistoryProvider.get_messages/save_messages` **must be `async`** | `core/orchestration/providers/history_provider.py` |
| Workflow routers must `ctx.send_message(...)`; `ctx.yield_output()` terminates the run | `core/orchestration/router.py` |
| Router output wrapped as `AgentExecutorRequest(messages, should_respond=True)` to preserve conversation chain | `core/orchestration/router.py` |
| MCP stdio command = `sys.executable`; server self-inserts project root into `sys.path` | `core/orchestration/agents/tier2_agent.py`, `src/mcp_server.py` |
| `mcp>=1.2,<2.0` pinned (SDK 2.x removed `FastMCP`) | `requirements.txt` |
