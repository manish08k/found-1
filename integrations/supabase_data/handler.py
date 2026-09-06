"""Supabase Data integration — direct database and storage operations."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _headers(config: dict) -> dict:
    return {
        "apikey": config.get("service_role_key", config.get("anon_key", "")),
        "Authorization": f"Bearer {config.get('service_role_key', config.get('anon_key', ''))}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base(config: dict) -> str:
    return config.get("url", "").rstrip("/")


@register_node("supabase_data.select")
async def supabase_data_select(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table = merged.get("table", "")
    params = {"select": merged.get("select", "*")}
    if merged.get("filter"):
        params.update(merged["filter"])
    if merged.get("limit"):
        params["limit"] = merged["limit"]
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{_base(merged)}/rest/v1/{table}", params=params)
        r.raise_for_status()
    return {"data": r.json(), "count": len(r.json())}


@register_node("supabase_data.insert")
async def supabase_data_insert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table = merged.get("table", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/rest/v1/{table}", json=merged.get("data", {}))
        r.raise_for_status()
    return {"data": r.json(), "inserted": True}


@register_node("supabase_data.update")
async def supabase_data_update(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table = merged.get("table", "")
    filter_col = merged.get("filter_column", "id")
    filter_val = merged.get("filter_value", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.patch(f"{_base(merged)}/rest/v1/{table}", params={filter_col: f"eq.{filter_val}"}, json=merged.get("data", {}))
        r.raise_for_status()
    return {"data": r.json(), "updated": True}


@register_node("supabase_data.delete")
async def supabase_data_delete(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table = merged.get("table", "")
    filter_col = merged.get("filter_column", "id")
    filter_val = merged.get("filter_value", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.delete(f"{_base(merged)}/rest/v1/{table}", params={filter_col: f"eq.{filter_val}"})
        r.raise_for_status()
    return {"deleted": True}
