"""Splitwise integration — expense splitting and tracking."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://secure.splitwise.com/api/v3.0"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("splitwise.get_expenses")
async def splitwise_get_expenses(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/get_expenses", params={"limit": merged.get("limit", 20)})
        r.raise_for_status()
    return {"expenses": r.json().get("expenses", [])}


@register_node("splitwise.create_expense")
async def splitwise_create_expense(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/create_expense", json={
            "description": merged.get("description", ""),
            "cost": merged.get("amount", "0.00"),
            "currency_code": merged.get("currency", "USD"),
            "group_id": merged.get("group_id", 0),
            "users__0__user_id": merged.get("user_id", ""),
            "users__0__paid_share": merged.get("amount", "0.00"),
            "users__0__owed_share": merged.get("amount", "0.00"),
        })
        r.raise_for_status()
    return r.json()
