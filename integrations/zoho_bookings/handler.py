"""Zoho Bookings appointment scheduling — handler for zoho_bookings integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.zohoapis.com/bookings/v1/json"


@register_node("zoho_bookings.list_workspaces")
async def zoho_bookings_list_workspaces(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List workspaces.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/getworkspaces", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_bookings.list_workspaces")
    return {"data": data}

@register_node("zoho_bookings.list_services")
async def zoho_bookings_list_services(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List services.

    config/input_data:
      api_key — API key or token (required)
      workspace_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workspace_id = merged.get("workspace_id") or ""
    if not workspace_id:
        raise ValueError("workspace_id required for zoho_bookings.list_services")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/getservices", headers=headers, params={"workspace_id": workspace_id})
        r.raise_for_status()
        data = r.json()
    log.info("zoho_bookings.list_services")
    return {"data": data}

@register_node("zoho_bookings.book_appointment")
async def zoho_bookings_book_appointment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Book an appointment.

    config/input_data:
      api_key — API key or token (required)
      service_id — (required)
      staff_id — (required)
      from_time — (required)
      customer_details — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    service_id = merged.get("service_id") or ""
    staff_id = merged.get("staff_id") or ""
    from_time = merged.get("from_time") or ""
    customer_details = merged.get("customer_details") or ""
    if not service_id or not staff_id or not from_time or not customer_details:
        raise ValueError("service_id, staff_id, from_time, customer_details required for zoho_bookings.book_appointment")
    payload = {"service_id": service_id, "staff_id": staff_id, "from_time": from_time, "customer_details": customer_details}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/bookappointment", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_bookings.book_appointment")
    return {"data": data}
