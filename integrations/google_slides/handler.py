"""Google Slides integration — presentation management."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://slides.googleapis.com/v1"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("google_slides.get_presentation")
async def google_slides_get_presentation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    pres_id = merged.get("presentation_id", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/presentations/{pres_id}")
        r.raise_for_status()
    data = r.json()
    return {"presentation_id": data["presentationId"], "title": data["title"], "slides": len(data.get("slides", []))}


@register_node("google_slides.create_presentation")
async def google_slides_create_presentation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/presentations", json={"title": merged.get("title", "New Presentation")})
        r.raise_for_status()
    data = r.json()
    return {"presentation_id": data["presentationId"], "title": data["title"],
            "url": f"https://docs.google.com/presentation/d/{data['presentationId']}"}


@register_node("google_slides.update_presentation")
async def google_slides_update_presentation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    pres_id = merged.get("presentation_id", "")
    requests = merged.get("requests", [])
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/presentations/{pres_id}:batchUpdate", json={"requests": requests})
        r.raise_for_status()
    return r.json()
