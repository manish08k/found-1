"""Mind Studio integration — AI agent builder."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://mindstudio.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("mind_studio.run_agent")
async def mind_studio_run_agent(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/run", json={
            "appId": merged.get("app_id", ""),
            "variables": merged.get("variables", {}),
        })
        r.raise_for_status()
    return r.json()
