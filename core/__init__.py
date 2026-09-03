"""
core/
─────
Central production-grade business logic for SupportPilot AI.

Sub-packages:
  guardrails/   — Input + output safety guardrails
  privacy/      — PII detection, redaction, retention policies
  middleware/   — HTTP + agent middleware (logging, auth, rate limiting)
  orchestration/— Agent routing, LLM client factory, prompts
  audit/        — Structured audit trail
"""
