"""Omnisend integration — ecommerce email marketing via Omnisend API v3."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

OMNISEND_BASE = "https://api.omnisend.com/v3"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"X-API-KEY": merged.get("api_key", "")}


@register_node("omnisend.list_contacts")
async def list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Omnisend.

    config/input_data:
      api_key — Omnisend API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=OMNISEND_BASE, timeout=30) as client:
        r = await client.get("/contacts", params={"limit": 25}, headers=headers)
        r.raise_for_status()
        data = r.json()
    contacts = data.get("contacts", [])
    log.info("omnisend.list_contacts", count=len(contacts))
    return {"contacts": contacts, "count": len(contacts)}


@register_node("omnisend.create_contact")
async def create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new subscribed contact in Omnisend.

    config/input_data:
      api_key — Omnisend API key (required)
      email   — Contact email address (required)
    """
    merged = {**config, **input_data}
    email = merged.get("email", "")
    if not email:
        raise ValueError("email is required for omnisend.create_contact")
    headers = _headers(config, input_data)
    payload = {
        "identifiers": [
            {
                "type": "email",
                "id": email,
                "channels": {"email": {"status": "subscribed"}},
            }
        ]
    }
    async with httpx.AsyncClient(base_url=OMNISEND_BASE, timeout=30) as client:
        r = await client.post("/contacts", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("omnisend.create_contact", email=email)
    return {"contact": data, "email": email}


@register_node("omnisend.list_campaigns")
async def list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List campaigns from Omnisend.

    config/input_data:
      api_key — Omnisend API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=OMNISEND_BASE, timeout=30) as client:
        r = await client.get("/campaigns", params={"limit": 25}, headers=headers)
        r.raise_for_status()
        data = r.json()
    campaigns = data.get("campaigns", [])
    log.info("omnisend.list_campaigns", count=len(campaigns))
    return {"campaigns": campaigns, "count": len(campaigns)}


@register_node("omnisend.add_contact_to_list")
async def add_contact_to_list(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a contact to an Omnisend list.

    config/input_data:
      api_key — Omnisend API key (required)
      list_id — ID of the list (required)
      email   — Contact email address (required)
    """
    merged = {**config, **input_data}
    list_id = merged.get("list_id", "")
    email = merged.get("email", "")
    if not list_id or not email:
        raise ValueError("list_id and email are required for omnisend.add_contact_to_list")
    headers = _headers(config, input_data)
    payload = {"email": email}
    async with httpx.AsyncClient(base_url=OMNISEND_BASE, timeout=30) as client:
        r = await client.post(f"/lists/{list_id}/subscribers", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json() if r.text else {}
    log.info("omnisend.add_contact_to_list", list_id=list_id, email=email)
    return {"result": data, "list_id": list_id, "email": email}
