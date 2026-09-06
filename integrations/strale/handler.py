"""Strale integration — multilingual translation and localization."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.strale.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("strale.translate_text")
async def strale_translate_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/translate", json={
            "text": merged.get("text", ""),
            "target_language": merged.get("target_language", "en"),
            "source_language": merged.get("source_language"),
        })
        r.raise_for_status()
    return r.json()


@register_node("strale.detect_language")
async def strale_detect_language(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/detect", json={"text": merged.get("text", "")})
        r.raise_for_status()
    return r.json()
