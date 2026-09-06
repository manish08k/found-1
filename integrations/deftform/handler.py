"""DeftForm integration — form builder and submissions."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.deftform.com/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("deftform.get_submissions")
async def deftform_get_submissions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    form_id = merged.get("form_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/forms/{form_id}/submissions")
        r.raise_for_status()
    return {"submissions": r.json()}


@register_node("deftform.get_form")
async def deftform_get_form(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    form_id = merged.get("form_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/forms/{form_id}")
        r.raise_for_status()
    return r.json()
