"""AskHandle AI customer support — Activepieces piece name — handler for ask_handle integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.askhandle.com/v1"


@register_node("ask_handle.create_ticket")
async def ask_handle_create_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create support ticket.

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
        raise ValueError("subject, description required for ask_handle.create_ticket")
    payload = {"subject": subject, "description": description}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/tickets", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("ask_handle.create_ticket")
    return {"data": data}

@register_node("ask_handle.list_tickets")
async def ask_handle_list_tickets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("ask_handle.list_tickets")
    return {"data": data}

@register_node("ask_handle.get_ticket")
async def ask_handle_get_ticket(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
        raise ValueError("ticket_id required for ask_handle.get_ticket")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/tickets/{ticket_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("ask_handle.get_ticket")
    return {"data": data}
