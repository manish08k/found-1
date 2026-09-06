"""Actual Budget personal finance tool — handler for actualbudget integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "http://localhost:5006/api/v1"


@register_node("actualbudget.list_budgets")
async def actualbudget_list_budgets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all budgets.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/budgets", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("actualbudget.list_budgets")
    return {"data": data}

@register_node("actualbudget.get_budget")
async def actualbudget_get_budget(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get budget details.

    config/input_data:
      api_key — API key or token (required)
      budget_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    budget_id = merged.get("budget_id") or ""
    if not budget_id:
        raise ValueError("budget_id required for actualbudget.get_budget")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/budgets/{budget_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("actualbudget.get_budget")
    return {"data": data}

@register_node("actualbudget.sync_budget")
async def actualbudget_sync_budget(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Sync a budget.

    config/input_data:
      api_key — API key or token (required)
      budget_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    budget_id = merged.get("budget_id") or ""
    if not budget_id:
        raise ValueError("budget_id required for actualbudget.sync_budget")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/budgets/{budget_id}/sync", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("actualbudget.sync_budget")
    return {"data": data}
