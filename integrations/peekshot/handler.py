"""Peekshot integration — website screenshot API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.peekshot.com/api/v1"


def _headers(config: dict) -> dict:
    return {"X-Api-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("peekshot.take_screenshot")
async def peekshot_take_screenshot(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/screenshots", json={
            "url": merged.get("url", ""),
            "width": merged.get("width", 1280),
            "height": merged.get("height", 800),
            "format": merged.get("format", "png"),
        })
        r.raise_for_status()
    return r.json()
