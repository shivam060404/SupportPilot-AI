"""
src/api/routes/services.py
──────────────────────────
Endpoints for checking IT service status.
"""
from fastapi import APIRouter
from src.api.schemas import ServicesStatusResponse, ServiceStatusItem
import json
from src.tools.check_service_status import check_service_status

router = APIRouter(prefix="/services", tags=["Services"])

@router.get(
    "/status",
    response_model=ServicesStatusResponse,
    summary="Get status of all major IT services",
)
async def get_services_status() -> ServicesStatusResponse:
    # We'll just call our own agent tool logic for consistency in this MVP
    services_to_check = ["VPN", "Email", "Jira", "Salesforce"]
    
    status_items = []
    for svc in services_to_check:
        # check_service_status returns JSON string
        result_str = check_service_status(svc)
        try:
            res = json.loads(result_str)
            status_items.append(ServiceStatusItem(
                service=res.get("service", svc),
                status=res.get("status", "Unknown"),
                message=res.get("message", "")
            ))
        except Exception:
            status_items.append(ServiceStatusItem(
                service=svc,
                status="Unknown",
                message="Error checking service."
            ))
            
    return ServicesStatusResponse(services=status_items)
