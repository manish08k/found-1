"""Pylon integration — customer operations platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.usepylon.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("pylon.create_issue")
async def pylon_create_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/issues", json={
            "title": merged.get("title", ""),
            "body": merged.get("body", ""),
            "assignee_id": merged.get("assignee_id", ""),
            "account_id": merged.get("account_id", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("pylon.get_issues")
async def pylon_get_issues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/issues", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"issues": r.json()}
