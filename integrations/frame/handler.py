"""Frame.io integration — video review and collaboration."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://api.frame.io/v2"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("frame.get_projects")
async def frame_get_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/projects")
        r.raise_for_status()
    return {"projects": r.json()}


@register_node("frame.create_review_link")
async def frame_create_review_link(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/review_links", json={
            "name": merged.get("name", "Review"),
            "project_id": merged.get("project_id", ""),
        })
        r.raise_for_status()
    return r.json()
