"""Clockodo integration — time tracking and workforce management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://my.clockodo.com/api"


def _headers(config: dict) -> dict:
    return {
        "X-ClockodoApiUser": config.get("email", ""),
        "X-ClockodoApiKey": config.get("api_key", ""),
        "Content-Type": "application/json",
    }


@register_node("clockodo.get_entries")
async def clockodo_get_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    params = {
        "time_since": merged.get("time_since", ""),
        "time_until": merged.get("time_until", ""),
    }
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/entries", params={k: v for k, v in params.items() if v})
        r.raise_for_status()
    return r.json()


@register_node("clockodo.create_entry")
async def clockodo_create_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/entries", json={
            "customers_id": merged.get("customers_id", ""),
            "services_id": merged.get("services_id", ""),
            "time_since": merged.get("time_since", ""),
            "time_until": merged.get("time_until", ""),
            "text": merged.get("text", ""),
        })
        r.raise_for_status()
    return r.json()
