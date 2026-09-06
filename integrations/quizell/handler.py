"""Quizell integration — interactive quizzes and product recommendations."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.quizell.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("quizell.get_quiz_results")
async def quizell_get_quiz_results(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    quiz_id = merged.get("quiz_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/quizzes/{quiz_id}/results")
        r.raise_for_status()
    return {"results": r.json()}


@register_node("quizell.get_leads")
async def quizell_get_leads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/leads", params={"limit": merged.get("limit", 50)})
        r.raise_for_status()
    return {"leads": r.json()}
