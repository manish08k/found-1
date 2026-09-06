"""Aidbase AI customer support platform — handler for aidbase integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.aidbase.ai/v1"


@register_node("aidbase.create_ticket")
async def aidbase_create_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a support ticket.

    config/input_data:
      api_key — API key or token (required)
      subject — (required)
      description — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    subject = merged.get("subject") or ""
    description = merged.get("description") or ""
    if not subject or not description:
        raise ValueError("subject, description required for aidbase.create_ticket")
    payload = {"subject": subject, "description": description}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/tickets", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("aidbase.create_ticket")
    return {"data": data}

@register_node("aidbase.list_tickets")
async def aidbase_list_tickets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List support tickets.

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
    log.info("aidbase.list_tickets")
    return {"data": data}

@register_node("aidbase.get_ticket")
async def aidbase_get_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
        raise ValueError("ticket_id required for aidbase.get_ticket")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tickets/{ticket_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("aidbase.get_ticket")
    return {"data": data}
