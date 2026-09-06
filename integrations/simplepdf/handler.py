"""SimplePDF form filling and PDF submission integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://simplepdf.eu/api/v1"


@register_node("simplepdf.fill_form")
async def simplepdf_fill_form(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fill a PDF form with provided field values."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    form_id = merged.get("form_id", "")
    if not form_id:
        raise ValueError("form_id is required")
    payload = {
        "fields": merged.get("fields", {}),
        "metadata": merged.get("metadata", {}),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/forms/{form_id}/submissions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()
    log.info("simplepdf.fill_form")
    return result


@register_node("simplepdf.list_forms")
async def simplepdf_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all PDF forms."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/forms",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simplepdf.list_forms")
    return result


@register_node("simplepdf.get_submissions")
async def simplepdf_get_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get submissions for a PDF form."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    form_id = merged.get("form_id", "")
    if not form_id:
        raise ValueError("form_id is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/forms/{form_id}/submissions",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"page": merged.get("page", 1), "per_page": merged.get("per_page", 20)},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simplepdf.get_submissions")
    return result
