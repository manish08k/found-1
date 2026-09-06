"""OpnForm integration — open-source form builder management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

OPNFORM_BASE = "https://api.opnform.com/v1"


def _opnform_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("opnform.list_forms")
async def opnform_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms in the OpnForm workspace.

    config:
      token — OpnForm API token (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")

    async with httpx.AsyncClient(base_url=OPNFORM_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_opnform_headers(token))
        r.raise_for_status()
        data = r.json()

    forms = data if isinstance(data, list) else data.get("forms", [])
    log.info("opnform.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("opnform.get_form")
async def opnform_get_form(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific OpnForm form.

    config:
      token   — OpnForm API token (required)
      form_id — form ID or slug to retrieve (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for opnform.get_form")

    async with httpx.AsyncClient(base_url=OPNFORM_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}",
            headers=_opnform_headers(token),
        )
        r.raise_for_status()
        form = r.json()

    log.info("opnform.get_form", form_id=form_id)
    return {"form": form, "form_id": form_id}


@register_node("opnform.list_submissions")
async def opnform_list_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List submissions for a specific OpnForm form.

    config:
      token   — OpnForm API token (required)
      form_id — form ID to fetch submissions for (required)
      page    — page number for pagination (optional)
      limit   — submissions per page (optional)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for opnform.list_submissions")

    params = {}
    if merged.get("page") is not None:
        params["page"] = merged["page"]
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]

    async with httpx.AsyncClient(base_url=OPNFORM_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}/submissions",
            headers=_opnform_headers(token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    submissions = data.get("data", data) if isinstance(data, dict) else data
    total = data.get("total") if isinstance(data, dict) else len(submissions)
    log.info("opnform.list_submissions", form_id=form_id, count=len(submissions))
    return {"submissions": submissions, "form_id": form_id, "count": len(submissions), "total": total}
