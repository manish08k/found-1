"""Rendex integration — document rendering and generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.rendex.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("rendex.render_template")
async def rendex_render_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/render", json={
            "template_id": merged.get("template_id", ""),
            "data": merged.get("data", {}),
            "format": merged.get("format", "pdf"),
        })
        r.raise_for_status()
    return r.json()
