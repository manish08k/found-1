"""Tally integration — forms and submissions."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TALLY_BASE = "https://api.tally.so"


def _tally_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("tally.list_forms")
async def tally_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Tally forms for the authenticated workspace.

    config:
      access_token — Tally API access token (required)
      page         — page number (optional, default 1)
      limit        — results per page (optional, default 20)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    if not access_token:
        raise ValueError("access_token is required for tally.list_forms")

    params = {"page": merged.get("page", 1), "limit": merged.get("limit", 20)}

    async with httpx.AsyncClient(base_url=TALLY_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_tally_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    forms = data.get("forms", data) if isinstance(data, dict) else data
    log.info("tally.list_forms", count=len(forms) if isinstance(forms, list) else 1)
    return {"forms": forms, "page": merged.get("page", 1)}


@register_node("tally.get_form")
async def tally_get_form(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Tally form.

    config:
      access_token — Tally API access token (required)
      form_id      — form ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    form_id = merged.get("form_id")
    if not access_token or not form_id:
        raise ValueError("access_token and form_id are required for tally.get_form")

    async with httpx.AsyncClient(base_url=TALLY_BASE, timeout=30) as client:
        r = await client.get(f"/forms/{form_id}", headers=_tally_headers(access_token))
        r.raise_for_status()
        form = r.json()

    log.info("tally.get_form", form_id=form_id)
    return {"form": form, "form_id": form_id}


@register_node("tally.get_submissions")
async def tally_get_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get submissions for a specific Tally form.

    config:
      access_token — Tally API access token (required)
      form_id      — form ID to retrieve submissions for (required)
      page         — page number (optional, default 1)
      limit        — results per page (optional, default 50)
      status       — filter by status: all/completed/in_progress (optional, default all)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    form_id = merged.get("form_id")
    if not access_token or not form_id:
        raise ValueError("access_token and form_id are required for tally.get_submissions")

    params: dict = {
        "page": merged.get("page", 1),
        "limit": merged.get("limit", 50),
    }
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=TALLY_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}/submissions",
            headers=_tally_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    submissions = data.get("submissions", data) if isinstance(data, dict) else data
    total = data.get("totalNumberOfSubmissions") if isinstance(data, dict) else None
    log.info("tally.get_submissions", form_id=form_id, count=len(submissions) if isinstance(submissions, list) else 1)
    return {"submissions": submissions, "form_id": form_id, "total": total}
