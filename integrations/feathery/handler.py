"""Feathery integration — form builder, submission, and user management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FEATHERY_BASE = "https://api.feathery.io/api"


def _feathery_headers(api_key: str) -> dict:
    return {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}


@register_node("feathery.list_forms")
async def feathery_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms in the Feathery account.

    config:
      api_key — Feathery API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    async with httpx.AsyncClient(base_url=FEATHERY_BASE, timeout=30) as client:
        r = await client.get("/form/", headers=_feathery_headers(api_key))
        r.raise_for_status()
        data = r.json()

    forms = data if isinstance(data, list) else data.get("results", [])
    log.info("feathery.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("feathery.get_submissions")
async def feathery_get_submissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get form submissions for a specific Feathery form.

    config:
      api_key — Feathery API key (required)
      form_id — form ID to fetch submissions for (required)
      page    — page number for pagination (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for feathery.get_submissions")

    params = {}
    if merged.get("page") is not None:
        params["page"] = merged["page"]

    async with httpx.AsyncClient(base_url=FEATHERY_BASE, timeout=30) as client:
        r = await client.get(
            f"/form/{form_id}/submission/",
            headers=_feathery_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    submissions = data.get("results", data) if isinstance(data, dict) else data
    total = data.get("count") if isinstance(data, dict) else len(submissions)
    log.info("feathery.get_submissions", form_id=form_id, count=len(submissions))
    return {"submissions": submissions, "form_id": form_id, "count": len(submissions), "total": total}


@register_node("feathery.get_users")
async def feathery_get_users(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get users/filler records from a Feathery form.

    config:
      api_key — Feathery API key (required)
      form_id — form ID to fetch users for (required)
      page    — page number for pagination (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for feathery.get_users")

    params = {}
    if merged.get("page") is not None:
        params["page"] = merged["page"]

    async with httpx.AsyncClient(base_url=FEATHERY_BASE, timeout=30) as client:
        r = await client.get(
            f"/form/{form_id}/user/",
            headers=_feathery_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    users = data.get("results", data) if isinstance(data, dict) else data
    total = data.get("count") if isinstance(data, dict) else len(users)
    log.info("feathery.get_users", form_id=form_id, count=len(users))
    return {"users": users, "form_id": form_id, "count": len(users), "total": total}
