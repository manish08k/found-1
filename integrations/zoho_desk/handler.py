"""Zoho Desk customer support — handler for zoho_desk integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://desk.zoho.com/api/v1"


@register_node("zoho_desk.list_tickets")
async def zoho_desk_list_tickets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tickets.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tickets", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_desk.list_tickets")
    return {"data": data}

@register_node("zoho_desk.create_ticket")
async def zoho_desk_create_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a ticket.

    config/input_data:
      api_key — API key or token (required)
      subject — (required)
      departmentId — (required)
      contactId — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    subject = merged.get("subject") or ""
    departmentId = merged.get("departmentId") or ""
    contactId = merged.get("contactId") or ""
    if not subject or not departmentId or not contactId:
        raise ValueError("subject, departmentId, contactId required for zoho_desk.create_ticket")
    payload = {"subject": subject, "departmentId": departmentId, "contactId": contactId}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/tickets", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_desk.create_ticket")
    return {"data": data}

@register_node("zoho_desk.get_ticket")
async def zoho_desk_get_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get ticket details.

    config/input_data:
      api_key — API key or token (required)
      ticket_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    ticket_id = merged.get("ticket_id") or ""
    if not ticket_id:
        raise ValueError("ticket_id required for zoho_desk.get_ticket")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tickets/{ticket_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_desk.get_ticket")
    return {"data": data}

@register_node("zoho_desk.update_ticket")
async def zoho_desk_update_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update a ticket.

    config/input_data:
      api_key — API key or token (required)
      ticket_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    ticket_id = merged.get("ticket_id") or ""
    if not ticket_id:
        raise ValueError("ticket_id required for zoho_desk.update_ticket")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(f"{BASE_URL}/tickets/{ticket_id}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zoho_desk.update_ticket")
    return {"data": data}
