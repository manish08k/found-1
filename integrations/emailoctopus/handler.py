"""EmailOctopus integration — email marketing via EmailOctopus API 1.6."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

EMAILOCTOPUS_BASE = "https://emailoctopus.com/api/1.6"


def _api_key(config: dict, input_data: dict) -> str:
    merged = {**config, **input_data}
    return merged.get("api_key", "")


@register_node("emailoctopus.list_lists")
async def list_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all email lists in EmailOctopus.

    config/input_data:
      api_key — EmailOctopus API key (required)
    """
    key = _api_key(config, input_data)
    async with httpx.AsyncClient(base_url=EMAILOCTOPUS_BASE, timeout=30) as client:
        r = await client.get("/lists", params={"api_key": key})
        r.raise_for_status()
        data = r.json()
    lists = data.get("data", [])
    log.info("emailoctopus.list_lists", count=len(lists))
    return {"lists": lists, "count": len(lists)}


@register_node("emailoctopus.list_contacts")
async def list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts for a specific list in EmailOctopus.

    config/input_data:
      api_key — EmailOctopus API key (required)
      list_id — List ID (required)
    """
    merged = {**config, **input_data}
    key = _api_key(config, input_data)
    list_id = merged.get("list_id", "")
    if not list_id:
        raise ValueError("list_id is required for emailoctopus.list_contacts")
    async with httpx.AsyncClient(base_url=EMAILOCTOPUS_BASE, timeout=30) as client:
        r = await client.get(
            f"/lists/{list_id}/contacts",
            params={"api_key": key, "limit": 100},
        )
        r.raise_for_status()
        data = r.json()
    contacts = data.get("data", [])
    log.info("emailoctopus.list_contacts", list_id=list_id, count=len(contacts))
    return {"contacts": contacts, "count": len(contacts), "list_id": list_id}


@register_node("emailoctopus.create_contact")
async def create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact in an EmailOctopus list.

    config/input_data:
      api_key       — EmailOctopus API key (required)
      list_id       — List ID (required)
      email_address — Contact email address (required)
      fields        — Additional fields dict (optional)
    """
    merged = {**config, **input_data}
    key = _api_key(config, input_data)
    list_id = merged.get("list_id", "")
    email_address = merged.get("email_address", "") or merged.get("email", "")
    if not list_id or not email_address:
        raise ValueError("list_id and email_address are required for emailoctopus.create_contact")
    payload = {
        "api_key": key,
        "email_address": email_address,
        "fields": merged.get("fields", {}),
        "status": "SUBSCRIBED",
    }
    async with httpx.AsyncClient(base_url=EMAILOCTOPUS_BASE, timeout=30) as client:
        r = await client.post(f"/lists/{list_id}/contacts", json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("emailoctopus.create_contact", list_id=list_id, email_address=email_address)
    return {"contact": data, "email_address": email_address, "list_id": list_id}
