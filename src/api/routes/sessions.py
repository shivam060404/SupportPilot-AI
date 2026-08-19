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
            # Depending on MAF version and serialization, we extract role and content
            # The 'type' field is usually 'UserMessage', 'AssistantMessage' etc.
            # or the model contains 'role' and 'content'
            
            # Simple heuristic extraction:
            role = "unknown"
            if "type" in msg:
                if "UserMessage" in msg["type"]:
                    role = "user"
                elif "Assistant" in msg["type"] or "Agent" in msg["type"]:
                    role = "assistant"
            
            content = msg.get("content", "")
            # Handle complex content if it's a list
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and "text" in p]
                content = " ".join(text_parts)
                
            parsed_messages.append(MessageHistoryItem(role=role, content=str(content)))
        except Exception:
            continue
            
    return SessionHistoryResponse(session_id=session_id, messages=parsed_messages)
