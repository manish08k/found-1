"""Fillout Forms integration — form and submission management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FILLOUT_BASE = "https://api.fillout.com/v1/api"


def _fillout_headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


@register_node("fillout_forms.list_forms")
async def fillout_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms in the Fillout account.

    config:
      api_key — Fillout API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    async with httpx.AsyncClient(base_url=FILLOUT_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_fillout_headers(api_key))
        r.raise_for_status()
        data = r.json()

    forms = data.get("forms", data) if isinstance(data, dict) else data
    log.info("fillout_forms.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("fillout_forms.get_submissions")
async def fillout_get_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get submissions for a specific Fillout form.

    config:
      api_key   — Fillout API key (required)
      form_id   — form ID to fetch submissions for (required)
      page_size — number of responses per page (optional)
      after_date — filter submissions after this date (optional)
      before_date — filter submissions before this date (optional)
      status    — submission status filter (optional, e.g. "finished")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for fillout_forms.get_submissions")

    params = {}
    if merged.get("page_size") is not None:
        params["pageSize"] = merged["page_size"]
    if merged.get("after_date"):
        params["afterDate"] = merged["after_date"]
    if merged.get("before_date"):
        params["beforeDate"] = merged["before_date"]
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=FILLOUT_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}/submissions",
            headers=_fillout_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    responses = data.get("responses", data) if isinstance(data, dict) else data
    total_count = data.get("totalResponses") if isinstance(data, dict) else len(responses)
    log.info("fillout_forms.get_submissions", form_id=form_id, count=len(responses))
    return {"submissions": responses, "form_id": form_id, "count": len(responses), "total_count": total_count}


@register_node("fillout_forms.get_form")
async def fillout_get_form(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Fillout form including its questions.

    config:
      api_key — Fillout API key (required)
      form_id — form ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for fillout_forms.get_form")

    async with httpx.AsyncClient(base_url=FILLOUT_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}",
            headers=_fillout_headers(api_key),
        )
        r.raise_for_status()
        form = r.json()

    log.info("fillout_forms.get_form", form_id=form_id)
    return {"form": form, "form_id": form_id}
