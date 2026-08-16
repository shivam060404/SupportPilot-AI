"""
src/tools/check_service_status.py
─────────────────────────────────
Tool to check service status.
"""
import agent_framework as af
import json

@af.tool(name="check_service_status", description="Check the status of a specific internal service (e.g., VPN, Email, Jira). Returns the current operational status.")
def check_service_status(service_name: str) -> str:
    """
    Check the simulated status of an IT service.
    
    Args:
        service_name: The name of the service to check.
        
    Returns:
        JSON string containing the status.
    """
    service_name_lower = service_name.lower()
    
    # Simulated status logic for MVP
    if "vpn" in service_name_lower:
        status = "Operational"
        message = "VPN gateways are currently operating normally."
    elif "email" in service_name_lower or "exchange" in service_name_lower:
        status = "Degraded Performance"
        message = "Some users are experiencing delays in receiving external emails."
    elif "jira" in service_name_lower or "confluence" in service_name_lower:
        status = "Operational"
        message = "All Atlassian services are operational."
    elif "salesforce" in service_name_lower:
        status = "Outage"
        message = "Salesforce is currently experiencing a known outage. Estimated time to recovery: 2 hours."
    else:
        status = "Operational"
        message = f"Service '{service_name}' appears to be operating normally."
        
    return json.dumps({
        "service": service_name,
        "status": status,
        "message": message
    })
