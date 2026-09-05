"""Drip integration — email marketing automation via Drip API v2."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DRIP_BASE = "https://api.getdrip.com/v2"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


def _account_id(config: dict, input_data: dict) -> str:
    merged = {**config, **input_data}
    account_id = merged.get("account_id", "")
    if not account_id:
        raise ValueError("account_id is required")
    return str(account_id)


@register_node("drip.list_subscribers")
async def list_subscribers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscribers for a Drip account.

    config/input_data:
      api_key    — Drip API key (required)
      account_id — Drip account ID (required)
    """
    account_id = _account_id(config, input_data)
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=DRIP_BASE, timeout=30) as client:
        r = await client.get(f"/{account_id}/subscribers", headers=headers)
        r.raise_for_status()
        data = r.json()
    subscribers = data.get("subscribers", [])
    log.info("drip.list_subscribers", account_id=account_id, count=len(subscribers))
    return {"subscribers": subscribers, "count": len(subscribers), "account_id": account_id}


@register_node("drip.create_subscriber")
async def create_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create or update a subscriber in Drip.

    config/input_data:
      api_key    — Drip API key (required)
      account_id — Drip account ID (required)
      email      — Subscriber email (required)
      first_name — Subscriber first name (optional)
    """
    merged = {**config, **input_data}
    account_id = _account_id(config, input_data)
    email = merged.get("email", "")
    first_name = merged.get("first_name", "")
    if not email:
        raise ValueError("email is required for drip.create_subscriber")
    headers = _headers(config, input_data)
    payload = {"subscribers": [{"email": email, "first_name": first_name}]}
    async with httpx.AsyncClient(base_url=DRIP_BASE, timeout=30) as client:
        r = await client.post(f"/{account_id}/subscribers", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("drip.create_subscriber", account_id=account_id, email=email)
    return {"subscribers": data.get("subscribers", []), "email": email}


@register_node("drip.tag_subscriber")
async def tag_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Apply a tag to a subscriber in Drip.

    config/input_data:
      api_key    — Drip API key (required)
      account_id — Drip account ID (required)
      email      — Subscriber email (required)
      tag        — Tag to apply (required)
    """
    merged = {**config, **input_data}
    account_id = _account_id(config, input_data)
    email = merged.get("email", "")
    tag = merged.get("tag", "")
    if not email or not tag:
        raise ValueError("email and tag are required for drip.tag_subscriber")
    headers = _headers(config, input_data)
    payload = {"tags": [{"email": email, "tag": tag}]}
    async with httpx.AsyncClient(base_url=DRIP_BASE, timeout=30) as client:
        r = await client.post(f"/{account_id}/tags", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json() if r.text else {}
    log.info("drip.tag_subscriber", account_id=account_id, email=email, tag=tag)
    return {"result": data, "email": email, "tag": tag}


@register_node("drip.list_campaigns")
async def list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all campaigns for a Drip account.

    config/input_data:
      api_key    — Drip API key (required)
      account_id — Drip account ID (required)
    """
    account_id = _account_id(config, input_data)
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=DRIP_BASE, timeout=30) as client:
        r = await client.get(f"/{account_id}/campaigns", headers=headers)
        r.raise_for_status()
        data = r.json()
    campaigns = data.get("campaigns", [])
    log.info("drip.list_campaigns", account_id=account_id, count=len(campaigns))
    return {"campaigns": campaigns, "count": len(campaigns), "account_id": account_id}
