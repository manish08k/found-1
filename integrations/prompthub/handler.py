"""PromptHub integration — prompt management and versioning."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.prompthub.us/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("prompthub.get_prompt")
async def prompthub_get_prompt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    prompt_id = merged.get("prompt_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/prompts/{prompt_id}")
        r.raise_for_status()
    return r.json()


@register_node("prompthub.list_prompts")
async def prompthub_list_prompts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/prompts")
        r.raise_for_status()
    return {"prompts": r.json()}


@register_node("prompthub.create_prompt")
async def prompthub_create_prompt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/prompts", json={
            "name": merged.get("name", ""),
            "content": merged.get("content", ""),
            "tags": merged.get("tags", []),
        })
        r.raise_for_status()
    return r.json()
