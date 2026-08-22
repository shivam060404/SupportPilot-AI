"""
src/tools/check_service_status.py
─────────────────────────────────
Tool to check service status.

Guardrail (spec §8): only allow-listed services may be queried. Anything else
is blocked *outside* the LLM and logged as a security event.
"""
import json

import agent_framework as af

from src.observability.logger import get_logger
from src.observability.tooltrace import traced_tool
from src.persistence.repositories import AuditLogRepository

log = get_logger(__name__)

# ── Allow-list (spec §8: "Allow-listed services") ────────────────────────────
SERVICE_ALLOWLIST = {
    "vpn",
    "email",
    "exchange",
    "jira",
    "confluence",
    "salesforce",
    "wifi",
    "printer",
}

# Simulated status registry for the MVP.
SERVICE_STATUS_REGISTRY = {
    "vpn": ("Operational", "VPN gateways are currently operating normally."),
    "email": ("Degraded Performance", "Some users are experiencing delays in receiving external emails."),
    "exchange": ("Degraded Performance", "Some users are experiencing delays in receiving external emails."),
    "jira": ("Operational", "All Atlassian services are operational."),
    "confluence": ("Operational", "All Atlassian services are operational."),
    "salesforce": ("Outage", "Salesforce is currently experiencing a known outage. Estimated time to recovery: 2 hours."),
    "wifi": ("Operational", "Corporate Wi-Fi is operating normally across all sites."),
    "printer": ("Operational", "Print services are operating normally."),
}


def _check_service_status_impl(service_name: str) -> str:
    service_name = (service_name or "").strip()
    service_name_lower = service_name.lower()

    if service_name_lower not in SERVICE_ALLOWLIST:
        AuditLogRepository.log_action(
            action="security_blocked_service_lookup",
            details={"service": service_name, "reason": "not_in_allowlist"},
        )
        log.warning("service_lookup_blocked", service=service_name)
        return json.dumps({
            "status": "blocked",
            "message": (
                f"Service '{service_name}' is not in the monitored services list. "
                f"Monitored services: {sorted(SERVICE_ALLOWLIST)}."
            ),
        })

    status, message = SERVICE_STATUS_REGISTRY.get(
        service_name_lower, ("Operational", f"Service '{service_name}' appears to be operating normally.")
    )
    return json.dumps({
        "service": service_name,
        "status": status,
        "message": message,
    })


@af.tool(name="check_service_status", description=(
    "Check the status of a specific internal service (VPN, Email, Jira, Salesforce, WiFi, Printer). "
    "Returns the current operational status. Only monitored services can be queried."
))
@traced_tool("check_service_status")
def check_service_status(service_name: str) -> str:
    """
    Check the status of an allow-listed internal IT service.

    Args:
        service_name: The name of the service to check (e.g., 'VPN', 'Email').
    """
    return _check_service_status_impl(service_name)
