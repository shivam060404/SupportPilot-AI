# SupportPilot AI

> **AI-powered IT Support Agent** built with **Microsoft Agent Framework (MAF) 1.14.0**, Groq LLaMA, FastAPI, and RAG.

```
Browser Chat UI
      ↓
   FastAPI
      ↓
Microsoft Agent Framework (MAF 1.14.0)
      ↓
     LLM (Groq LLaMA 3.3-70B)
   ↙  ↓   ↘
 RAG Tools MCP          ← Phase 2 / 4
      ↓
 Ticket / Service DB    ← Phase 2
```

---

## Phases

| Phase | Status | Focus |
|-------|--------|-------|
| **Phase 1** | ✅ Complete | Single MAF Agent + Groq + FastAPI + Web UI |
| Phase 2 | 🔜 | RAG + Knowledge Base + Tools + SQLite |
| Phase 3 | 🔜 | Sessions/State + Full API |
| Phase 4 | 🔜 | MCP + Incident Workflow |
| Phase 5 | 🔜 | Human Approval + Escalation |
| Phase 6 | 🔜 | Tests + Observability + Docker |

---

## Quick Start (Phase 1)

### 1. Prerequisites
- Python 3.11+ (tested on 3.14)
- A free [Groq API key](https://console.groq.com)

### 2. Clone & set up environment

```bash
git clone <repo-url>
cd "SupportPilot AI"

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and set your real GROQ_API_KEY
```

`.env.example` shows all available variables. **Never commit `.env`.**

### 4. Run the server

```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn src.api.main:app --reload --port 8000
```

### 5. Open the chat UI

Visit **http://localhost:8000** in your browser.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Browser chat UI |
| `/api/v1/chat` | POST | Send a message to the agent |
| `/api/v1/health` | GET | Liveness check |
| `/api/docs` | GET | Swagger UI |
| `/api/redoc` | GET | ReDoc docs |

### POST /api/v1/chat

```json
// Request
{
  "message": "My VPN keeps disconnecting every 10 minutes.",
  "session_id": "optional-uuid-for-multi-turn"
}

// Response
{
  "session_id": "550e8400-...",
  "response": "⏳ IN PROGRESS — ...",
  "trace_id": "abc123...",
  "phase": "Phase 1"
}
```

---

## Running Tests

```bash
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

---

## Project Structure

```
SupportPilot AI/
├── .env.example            # Env variable template (no secrets)
├── .gitignore
├── requirements.txt
├── pytest.ini
│
├── config/
│   └── __init__.py         # Pydantic Settings (all config here)
│
├── static/
│   ├── index.html          # Browser chat UI
│   └── styles.css          # Dark, premium CSS
│
├── src/
│   ├── agents/
│   │   ├── prompts.py      # IT support system prompt
│   │   └── supervisor_agent.py  # MAF harness agent (Groq)
│   │
│   ├── api/
│   │   ├── main.py         # FastAPI app entry point
│   │   ├── schemas.py      # Pydantic request/response models
│   │   └── routes/
│   │       └── chat.py     # POST /chat, GET /health
│   │
│   └── observability/
│       └── logger.py       # Structured logging (structlog)
│
└── tests/
    └── test_phase1.py      # Phase 1 test suite (7 tests)
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Agent Framework | Microsoft Agent Framework | 1.14.0 |
| LLM | Groq LLaMA 3.3-70B | via API |
| API | FastAPI + uvicorn | 0.138 / 0.52 |
| Settings | pydantic-settings | 2.15 |
| Logging | structlog | 26.1 |
| Testing | pytest + pytest-asyncio | 9.1 / 1.4 |
| Python | Python 3.11+ | 3.14 tested |

---

## Security Notes

- API keys live **only** in `.env` — never in source code or commits
- `.env` is in `.gitignore`
- Tool allow-lists and authorization checks (Phase 2+) are enforced outside the LLM
- No arbitrary SQL/shell access by the agent

---

## Architecture Decisions

**Why MAF?** Microsoft Agent Framework 1.14.0 is the unified successor to AutoGen and Semantic Kernel. It provides a production-ready agent harness, multi-turn session management, built-in MCP support, and graph-based workflow orchestration — all core requirements for this project.

**Why Groq?** Groq provides an OpenAI-compatible REST API. MAF's `OpenAIChatClient` works directly with Groq by setting `base_url=https://api.groq.com/openai/v1`, requiring no custom adapter.

**One agent per session** means concurrent users get isolated history providers — safe without global locks.
