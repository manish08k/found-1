"""PromptMate integration — AI prompt engineering assistant."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.promptmate.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("promptmate.run_prompt")
async def promptmate_run_prompt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/run", json={
            "prompt_id": merged.get("prompt_id", ""),
            "variables": merged.get("variables", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("promptmate.optimize_prompt")
async def promptmate_optimize_prompt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/optimize", json={"prompt": merged.get("prompt", "")})
        r.raise_for_status()
    return r.json()
