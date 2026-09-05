"""Nuelink integration — social media scheduling via Nuelink API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

NUELINK_BASE = "https://app.nuelink.com/api/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("nuelink.create_post")
async def create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create and schedule a social media post via Nuelink.

    config/input_data:
      api_key      — Nuelink API key (required)
      content      — Post text content (required)
      account_ids  — List of social account IDs (required)
      schedule_date — ISO 8601 date/time for scheduling (optional)
    """
    merged = {**config, **input_data}
    content = merged.get("content", "") or merged.get("text", "")
    account_ids = merged.get("account_ids", [])
    if not content or not account_ids:
        raise ValueError("content and account_ids are required for nuelink.create_post")
    headers = _headers(config, input_data)
    payload: dict = {"content": content, "account_ids": account_ids}
    schedule_date = merged.get("schedule_date", "")
    if schedule_date:
        payload["schedule_date"] = schedule_date
    async with httpx.AsyncClient(base_url=NUELINK_BASE, timeout=30) as client:
        r = await client.post("/posts", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("nuelink.create_post", account_count=len(account_ids))
    return {"post": data, "content": content}


@register_node("nuelink.list_accounts")
async def list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List connected social accounts in Nuelink.

    config/input_data:
      api_key — Nuelink API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=NUELINK_BASE, timeout=30) as client:
        r = await client.get("/accounts", headers=headers)
        r.raise_for_status()
        data = r.json()
    accounts = data.get("accounts", data) if isinstance(data, dict) else data
    log.info("nuelink.list_accounts")
    return {"accounts": accounts}


@register_node("nuelink.list_posts")
async def list_posts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List scheduled posts in Nuelink.

    config/input_data:
      api_key — Nuelink API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=NUELINK_BASE, timeout=30) as client:
        r = await client.get("/posts", params={"page": 1}, headers=headers)
        r.raise_for_status()
        data = r.json()
    posts = data.get("posts", data) if isinstance(data, dict) else data
    log.info("nuelink.list_posts")
    return {"posts": posts}
