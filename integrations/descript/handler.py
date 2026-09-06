"""Descript integration — audio/video editing and transcription."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.descript.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("descript.create_project")
async def descript_create_project(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/projects", json={"name": merged.get("name", "New Project")})
        r.raise_for_status()
    return r.json()


@register_node("descript.get_transcript")
async def descript_get_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    project_id = merged.get("project_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/projects/{project_id}/transcript")
        r.raise_for_status()
    return r.json()
