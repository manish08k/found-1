"""Youform form builder — handler for youform integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.youform.com/v1"


@register_node("youform.list_forms")
async def youform_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List forms.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/forms", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("youform.list_forms")
    return {"data": data}

@register_node("youform.get_form")
async def youform_get_form(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get form details.

    config/input_data:
      api_key — API key or token (required)
      form_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    form_id = merged.get("form_id") or ""
    if not form_id:
        raise ValueError("form_id required for youform.get_form")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/forms/{form_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("youform.get_form")
    return {"data": data}

@register_node("youform.list_submissions")
async def youform_list_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List form submissions.

    config/input_data:
      api_key — API key or token (required)
      form_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    form_id = merged.get("form_id") or ""
    if not form_id:
        raise ValueError("form_id required for youform.list_submissions")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/forms/{form_id}/submissions", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("youform.list_submissions")
    return {"data": data}
