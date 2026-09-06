"""Sendr integration — email automation platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.sendr.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("sendr.send_email")
async def sendr_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/emails", json={
            "to": merged.get("to", ""),
            "subject": merged.get("subject", ""),
            "content": merged.get("content", ""),
            "template_id": merged.get("template_id"),
        })
        r.raise_for_status()
    return r.json()


@register_node("sendr.create_sequence")
async def sendr_create_sequence(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/sequences", json={
            "name": merged.get("name", ""),
            "steps": merged.get("steps", []),
        })
        r.raise_for_status()
    return r.json()
