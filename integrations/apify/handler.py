"""Apify integration — web scraping and automation actors."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.apify.com/v2"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_token', '')}", "Content-Type": "application/json"}


@register_node("apify.run_actor")
async def apify_run_actor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    actor_id = merged.get("actor_id", "")
    run_input = merged.get("input", {})
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/acts/{actor_id}/runs", json=run_input)
        r.raise_for_status()
    return r.json().get("data", {})


@register_node("apify.get_run")
async def apify_get_run(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    run_id = merged.get("run_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/actor-runs/{run_id}")
        r.raise_for_status()
    return r.json().get("data", {})


@register_node("apify.get_dataset_items")
async def apify_get_dataset_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    dataset_id = merged.get("dataset_id", "")
    limit = merged.get("limit", 100)
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/datasets/{dataset_id}/items", params={"limit": limit})
        r.raise_for_status()
    return {"items": r.json()}


@register_node("apify.list_actors")
async def apify_list_actors(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/acts")
        r.raise_for_status()
    return {"actors": r.json().get("data", {}).get("items", [])}
