"""
config/__init__.py
──────────────────
Centralised application settings loaded from environment variables.
All other modules import from here:  `from config import get_settings`
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = Field(default="SupportPilot AI")
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    secret_key: str = Field(default="change-me")

    # ── API ──────────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    cors_origins: str = Field(
        default="http://localhost:8000,http://127.0.0.1:8000"
    )

    # ── LLM (Groq — OpenAI-compatible endpoint) ───────────────────────────────
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(default=f"sqlite:///{ROOT_DIR}/supportpilot.db")

    # ── Vector Store (Phase 2) ───────────────────────────────────────────────
    chroma_persist_dir: str = Field(default=str(ROOT_DIR / "data" / "chroma"))
    embedding_model: str = Field(default="all-MiniLM-L6-v2")

    # ── MCP (Phase 4) ────────────────────────────────────────────────────────
    mcp_server_port: int = Field(default=9000)

    # ── OpenTelemetry (Phase 6) ──────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4317")
    otel_service_name: str = Field(default="supportpilot-ai")

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @field_validator("groq_api_key")
    @classmethod
    def warn_missing_key(cls, v: str) -> str:
        if not v:
            import warnings
            warnings.warn(
                "GROQ_API_KEY is not set — the LLM agent will not function.",
                stacklevel=2,
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance — import this everywhere."""
    return Settings()
