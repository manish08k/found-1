"""Formsite integration — form management and result retrieval."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _formsite_base(server: str, username: str) -> str:
    return f"https://{server}.formsite.com/api/v2/{username}"


def _formsite_headers(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}


@register_node("formsite.list_forms")
async def formsite_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms in a Formsite account.

    config:
      server    — Formsite server code (required, e.g. "fs25")
      username  — Formsite username/directory (required)
      api_token — Formsite API token (required)
      page      — page number for pagination (optional)
      limit     — results per page (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    server = merged.get("server")
    username = merged.get("username")
    if not server:
        raise ValueError("server is required for formsite.list_forms")
    if not username:
        raise ValueError("username is required for formsite.list_forms")

    params = {}
    if merged.get("page") is not None:
        params["page"] = merged["page"]
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]

    base_url = _formsite_base(server, username)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/forms",
            headers=_formsite_headers(api_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    forms = data.get("forms", data) if isinstance(data, dict) else data
    log.info("formsite.list_forms", server=server, username=username, count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("formsite.get_results")
async def formsite_get_results(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get form submission results from Formsite.

    config:
      server    — Formsite server code (required, e.g. "fs25")
      username  — Formsite username/directory (required)
      api_token — Formsite API token (required)
      form_id   — form ID to fetch results for (required)
      page      — page number (optional)
      limit     — results per page (optional)
      date_start — filter results after this date (optional)
      date_end   — filter results before this date (optional)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    server = merged.get("server")
    username = merged.get("username")
    form_id = merged.get("form_id")
    if not server:
        raise ValueError("server is required for formsite.get_results")
    if not username:
        raise ValueError("username is required for formsite.get_results")
    if not form_id:
        raise ValueError("form_id is required for formsite.get_results")

    params = {}
    if merged.get("page") is not None:
        params["page"] = merged["page"]
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]
    if merged.get("date_start"):
        params["date_start"] = merged["date_start"]
    if merged.get("date_end"):
        params["date_end"] = merged["date_end"]

    base_url = _formsite_base(server, username)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/forms/{form_id}/results",
            headers=_formsite_headers(api_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    results = data.get("results", data) if isinstance(data, dict) else data
    log.info("formsite.get_results", form_id=form_id, count=len(results))
    return {"results": results, "form_id": form_id, "count": len(results)}


@register_node("formsite.get_form_items")
async def formsite_get_form_items(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get form items (questions/fields) for a specific Formsite form.

    config:
      server    — Formsite server code (required, e.g. "fs25")
      username  — Formsite username/directory (required)
      api_token — Formsite API token (required)
      form_id   — form ID to fetch items for (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    server = merged.get("server")
    username = merged.get("username")
    form_id = merged.get("form_id")
    if not server:
        raise ValueError("server is required for formsite.get_form_items")
    if not username:
        raise ValueError("username is required for formsite.get_form_items")
    if not form_id:
        raise ValueError("form_id is required for formsite.get_form_items")

    base_url = _formsite_base(server, username)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/forms/{form_id}/items",
            headers=_formsite_headers(api_token),
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("items", data) if isinstance(data, dict) else data
    log.info("formsite.get_form_items", form_id=form_id, count=len(items))
    return {"items": items, "form_id": form_id, "count": len(items)}
