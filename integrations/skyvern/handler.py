"""Skyvern integration — AI browser automation agent."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.skyvern.com/api/v1"


def _headers(config: dict) -> dict:
    return {"x-api-key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("skyvern.run_task")
async def skyvern_run_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/tasks", json={
            "url": merged.get("url", ""),
            "navigation_goal": merged.get("goal", ""),
            "data_extraction_goal": merged.get("extraction_goal", ""),
            "navigation_payload": merged.get("payload", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("skyvern.get_task")
async def skyvern_get_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    task_id = merged.get("task_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/tasks/{task_id}")
        r.raise_for_status()
    return r.json()
