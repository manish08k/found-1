"""SendFox integration — email marketing via SendFox API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SENDFOX_BASE = "https://sendfox.com/api"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("sendfox.list_lists")
async def list_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all contact lists in SendFox.

    config/input_data:
      api_key — SendFox API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=SENDFOX_BASE, timeout=30) as client:
        r = await client.get("/lists", headers=headers)
        r.raise_for_status()
        data = r.json()
    lists = data.get("data", data) if isinstance(data, dict) else data
    log.info("sendfox.list_lists", count=len(lists) if isinstance(lists, list) else 1)
    return {"lists": lists}


@register_node("sendfox.create_contact")
async def create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact in SendFox and add to a list.

    config/input_data:
      api_key    — SendFox API key (required)
      email      — Contact email address (required)
      first_name — Contact first name (optional)
      last_name  — Contact last name (optional)
      list_id    — List ID to add the contact to (optional)
    """
    merged = {**config, **input_data}
    email = merged.get("email", "")
    if not email:
        raise ValueError("email is required for sendfox.create_contact")
    headers = _headers(config, input_data)
    payload: dict = {
        "email": email,
        "first_name": merged.get("first_name", ""),
        "last_name": merged.get("last_name", ""),
    }
    list_id = merged.get("list_id")
    if list_id:
        payload["lists"] = [list_id]
    async with httpx.AsyncClient(base_url=SENDFOX_BASE, timeout=30) as client:
        r = await client.post("/contacts", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("sendfox.create_contact", email=email)
    return {"contact": data, "email": email}


@register_node("sendfox.list_campaigns")
async def list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all campaigns in SendFox.

    config/input_data:
      api_key — SendFox API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=SENDFOX_BASE, timeout=30) as client:
        r = await client.get("/campaigns", headers=headers)
        r.raise_for_status()
        data = r.json()
    campaigns = data.get("data", data) if isinstance(data, dict) else data
    log.info("sendfox.list_campaigns")
    return {"campaigns": campaigns}
