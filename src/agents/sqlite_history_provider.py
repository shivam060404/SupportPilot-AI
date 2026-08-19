"""
src/agents/sqlite_history_provider.py
─────────────────────────────────────
Custom MAF HistoryProvider that persists conversation state to SQLite.
"""
from typing import Any, Sequence
import agent_framework as af
from src.persistence.repositories import SessionRepository
from src.observability.logger import get_logger

log = get_logger(__name__)

class SQLiteHistoryProvider(af.HistoryProvider):
    def __init__(self, source_id: str = "sqlite-history-provider", **kwargs):
        super().__init__(source_id, **kwargs)

    def get_messages(self, session_id: str | None, *, state: dict[str, Any] | None = None, **kwargs: Any) -> list[af.Message]:
        if not session_id:
            return []
            
        json_messages = SessionRepository.get_messages(session_id)
        messages = []
        for msg_json in json_messages:
            try:
                # Deserialize JSON back into MAF Message objects
                messages.append(af.Message.from_json(msg_json))
            except Exception as e:
                log.error("deserialize_message_error", error=str(e), session_id=session_id)
                
        log.debug("retrieved_history", session_id=session_id, count=len(messages))
        return messages

    def save_messages(self, session_id: str | None, messages: Sequence[af.Message], *, state: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not session_id or not messages:
            return
            
        json_messages = []
        for msg in messages:
            try:
                # Serialize MAF Message objects to JSON
                json_messages.append(msg.to_json())
            except Exception as e:
                log.error("serialize_message_error", error=str(e), session_id=session_id)
                
        SessionRepository.save_messages(session_id, json_messages)
        log.debug("saved_history", session_id=session_id, count=len(json_messages))
