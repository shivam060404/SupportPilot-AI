"""
src/api/routes/sessions.py
──────────────────────────
Endpoints for session history management.
"""
from fastapi import APIRouter
from src.persistence.repositories import SessionRepository
from src.api.schemas import SessionHistoryResponse, MessageHistoryItem
import json

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.get(
    "/{session_id}/history",
    response_model=SessionHistoryResponse,
    summary="Get chat history for a session",
)
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    raw_messages = SessionRepository.get_messages(session_id)
    
    parsed_messages = []
    for raw in raw_messages:
        try:
            msg = json.loads(raw)
            # Prefer the standard "role" field; fall back to MAF type names.
            role = msg.get("role", "").lower()
            if not role or role == "unknown":
                mtype = msg.get("type", "")
                if "user" in mtype.lower():
                    role = "user"
                elif "assistant" in mtype.lower() or "agent" in mtype.lower():
                    role = "assistant"
                else:
                    role = "unknown"

            content = msg.get("contents", msg.get("content", ""))
            # Handle complex content if it's a list of content parts
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and "text" in p]
                content = " ".join(text_parts)
            elif isinstance(content, dict):
                content = content.get("text", "")

            parsed_messages.append(MessageHistoryItem(role=role, content=str(content)))
        except Exception:
            continue
            
    return SessionHistoryResponse(session_id=session_id, messages=parsed_messages)
