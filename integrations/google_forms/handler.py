"""Google Forms integration — form creation and response retrieval."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://forms.googleapis.com/v1"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("google_forms.get_form")
async def google_forms_get_form(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    form_id = merged.get("form_id", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/forms/{form_id}")
        r.raise_for_status()
    return r.json()


@register_node("google_forms.get_responses")
async def google_forms_get_responses(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    form_id = merged.get("form_id", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/forms/{form_id}/responses")
        r.raise_for_status()
    data = r.json()
    return {"responses": data.get("responses", []), "total": data.get("totalSize", 0)}
