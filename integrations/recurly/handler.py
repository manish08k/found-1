"""Recurly integration — subscription management and billing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://v3.recurly.com"


def _headers(config: dict) -> dict:
    import base64
    api_key = config.get("api_key", "")
    encoded = base64.b64encode(f"{api_key}:".encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Accept": "application/vnd.recurly.v2021-02-25+json", "Content-Type": "application/json"}


@register_node("recurly.create_subscription")
async def recurly_create_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/subscriptions", json={
            "plan_code": merged.get("plan_code", ""),
            "account": {"code": merged.get("account_code", ""), "email": merged.get("email", "")},
        })
        r.raise_for_status()
    return r.json()


@register_node("recurly.get_subscription")
async def recurly_get_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    sub_id = merged.get("subscription_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/subscriptions/{sub_id}")
        r.raise_for_status()
    return r.json()


@register_node("recurly.cancel_subscription")
async def recurly_cancel_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    sub_id = merged.get("subscription_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.delete(f"{BASE}/subscriptions/{sub_id}")
        r.raise_for_status()
    return {"subscription_id": sub_id, "status": "cancelled"}
