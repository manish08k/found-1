"""EasyPeasy AI integration — AI content generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.easypeasy.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("easy_peasy_ai.generate_content")
async def easy_peasy_ai_generate_content(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/generate", json={
            "prompt": merged.get("prompt", ""),
            "template": merged.get("template", ""),
            "max_tokens": merged.get("max_tokens", 500),
        })
        r.raise_for_status()
    return r.json()
