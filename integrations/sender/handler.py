"""Sender integration — email marketing via Sender API v2."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SENDER_BASE = "https://api.sender.net/v2"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_token', merged.get('api_key', ''))}"}


@register_node("sender.list_subscribers")
async def list_subscribers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscribers in Sender.

    config/input_data:
      api_token — Sender API token (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=SENDER_BASE, timeout=30) as client:
        r = await client.get("/subscribers", params={"page": 1, "limit": 25}, headers=headers)
        r.raise_for_status()
        data = r.json()
    subscribers = data.get("data", [])
    log.info("sender.list_subscribers", count=len(subscribers))
    return {"subscribers": subscribers, "count": len(subscribers)}


@register_node("sender.create_subscriber")
async def create_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a subscriber in Sender.

    config/input_data:
      api_token  — Sender API token (required)
      email      — Subscriber email (required)
      first_name — First name (optional)
      last_name  — Last name (optional)
      group_id   — Group ID to add subscriber to (optional)
    """
    merged = {**config, **input_data}
    email = merged.get("email", "")
    if not email:
        raise ValueError("email is required for sender.create_subscriber")
    headers = _headers(config, input_data)
    payload: dict = {
        "email": email,
        "firstname": merged.get("first_name", ""),
        "lastname": merged.get("last_name", ""),
    }
    group_id = merged.get("group_id")
    if group_id:
        payload["groups"] = [group_id]
    async with httpx.AsyncClient(base_url=SENDER_BASE, timeout=30) as client:
        r = await client.post("/subscribers", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("sender.create_subscriber", email=email)
    return {"subscriber": data.get("data", data), "email": email}


@register_node("sender.list_groups")
async def list_groups(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscriber groups in Sender.

    config/input_data:
      api_token — Sender API token (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=SENDER_BASE, timeout=30) as client:
        r = await client.get("/groups", headers=headers)
        r.raise_for_status()
        data = r.json()
    groups = data.get("data", [])
    log.info("sender.list_groups", count=len(groups))
    return {"groups": groups, "count": len(groups)}
