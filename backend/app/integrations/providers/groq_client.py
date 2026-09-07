"""
core/orchestration/groq_client.py
──────────────────────────────────
Clean Groq-compatible OpenAI client factory.

Uses the `openai` SDK directly with Groq's base_url (standard chat/completions).
MAF's OpenAIChatCompletionClient is used as the wrapper since it accepts
base_url + api_key overrides.

This module is the single place where the Groq API compatibility is handled.
If Groq adds a new incompatible parameter, fix it here — nowhere else.
"""
from __future__ import annotations

from typing import Optional

from agent_framework_openai import OpenAIChatCompletionClient

from config import get_settings
from src.observability.logger import get_logger

log = get_logger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def create_groq_client(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> OpenAIChatCompletionClient:
    """
    Create a MAF-compatible LLM client pointed at Groq.

    Args:
        model: Model name (e.g. 'openai/gpt-oss-120b'). Defaults to settings.
        api_key: Groq API key. Defaults to settings.
        base_url: Groq base URL. Defaults to Groq's chat/completions endpoint.

    Returns:
        Configured OpenAIChatCompletionClient for use with MAF agents.

    Raises:
        ValueError: If no API key is configured.
    """
    settings = get_settings()
    resolved_model = model or settings.groq_model
    resolved_key = api_key or settings.groq_api_key
    resolved_url = base_url or settings.groq_base_url or _GROQ_BASE_URL

    if not resolved_key:
        raise ValueError(
            "GROQ_API_KEY is not configured. Set it in .env and restart the server."
        )

    log.debug(
        "groq_client_created",
        model=resolved_model,
        base_url=resolved_url,
    )

    return OpenAIChatCompletionClient(
        model=resolved_model,
        api_key=resolved_key,
        base_url=resolved_url,
    )


def is_groq_configured() -> bool:
    """Check if Groq API key is configured without raising."""
    settings = get_settings()
    return bool(settings.groq_api_key)
