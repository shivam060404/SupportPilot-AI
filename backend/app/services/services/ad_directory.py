"""
src/services/ad_directory.py
────────────────────────────
Mock Active Directory business logic.

Single source of truth shared by:
  • the MCP stdio server (src/mcp_server.py) — LLM-facing lookup tools
  • the guarded executor tool (execute_approved_action) — code-enforced path

Sensitive operations (unlock_account) are plain functions here; whether they may
run is decided by callers, never by the LLM.
"""
from __future__ import annotations


def check_account_status(email: str) -> str:
    email = (email or "").strip()
    if not email or "@" not in email:
        return "ERROR: A valid company email address is required."
    email_lower = email.lower()
    if "locked" in email_lower:
        return f"Account for {email} is LOCKED due to multiple failed login attempts."
    elif "disabled" in email_lower:
        return f"Account for {email} is DISABLED."
    return f"Account for {email} is ACTIVE and in good standing."


def get_manager_info(email: str) -> str:
    email = (email or "").strip()
    if not email or "@" not in email:
        return "ERROR: A valid company email address is required."
    if "ceo" in email.lower():
        return "No manager found. User is the CEO."
    return f"manager.of.{email.split('@')[0]}@company.com"


def unlock_account(email: str) -> str:
    """SENSITIVE. In a real system this would hit the AD API."""
    email = (email or "").strip()
    if not email or "@" not in email:
        return "ERROR: A valid company email address is required."
    return f"SUCCESS: The account for {email} has been successfully unlocked."
