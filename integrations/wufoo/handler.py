"""Wufoo integration — form listings, entries, and submissions."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _wufoo_base(subdomain: str) -> str:
    return f"https://{subdomain}.wufoo.com/api/v3"


@register_node("wufoo.list_forms")
async def wufoo_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Wufoo forms for the account.

    config:
      subdomain — Wufoo account subdomain (required)
      api_key   — Wufoo API key (required)
    """
    merged = {**config, **input_data}
    subdomain = merged.get("subdomain", "")
    api_key = merged.get("api_key", "")
    auth = httpx.BasicAuth(api_key, "footastic")

    async with httpx.AsyncClient(base_url=_wufoo_base(subdomain), timeout=30) as client:
        r = await client.get("/forms.json", auth=auth)
        r.raise_for_status()
        data = r.json()

    forms = data.get("Forms", [])
    log.info("wufoo.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("wufoo.get_form")
async def wufoo_get_form(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Wufoo form.

    config:
      subdomain — Wufoo account subdomain (required)
      api_key   — Wufoo API key (required)
      form_hash — unique form identifier (required)
    """
    merged = {**config, **input_data}
    subdomain = merged.get("subdomain", "")
    api_key = merged.get("api_key", "")
    form_hash = merged.get("form_hash")
    if not form_hash:
        raise ValueError("form_hash is required for wufoo.get_form")

    auth = httpx.BasicAuth(api_key, "footastic")

    async with httpx.AsyncClient(base_url=_wufoo_base(subdomain), timeout=30) as client:
        r = await client.get(f"/forms/{form_hash}.json", auth=auth)
        r.raise_for_status()
        data = r.json()

    forms = data.get("Forms", [])
    form = forms[0] if forms else {}
    log.info("wufoo.get_form", form_hash=form_hash)
    return {"form": form, "form_hash": form_hash}


@register_node("wufoo.get_entries")
async def wufoo_get_entries(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get form entries with optional filtering and pagination.

    config:
      subdomain  — Wufoo account subdomain (required)
      api_key    — Wufoo API key (required)
      form_hash  — unique form identifier (required)
      filter     — optional filter string
      page_start — pagination start index (default 0)
      page_size  — entries per page (default 25)
    """
    merged = {**config, **input_data}
    subdomain = merged.get("subdomain", "")
    api_key = merged.get("api_key", "")
    form_hash = merged.get("form_hash")
    if not form_hash:
        raise ValueError("form_hash is required for wufoo.get_entries")

    params: dict = {
        "pageStart": merged.get("page_start", 0),
        "pageSize": merged.get("page_size", 25),
    }
    if merged.get("filter"):
        params["filter"] = merged["filter"]

    auth = httpx.BasicAuth(api_key, "footastic")

    async with httpx.AsyncClient(base_url=_wufoo_base(subdomain), timeout=30) as client:
        r = await client.get(f"/forms/{form_hash}/entries.json", auth=auth, params=params)
        r.raise_for_status()
        data = r.json()

    entries = data.get("Entries", [])
    log.info("wufoo.get_entries", form_hash=form_hash, count=len(entries))
    return {"entries": entries, "count": len(entries), "form_hash": form_hash}


@register_node("wufoo.get_entry_count")
async def wufoo_get_entry_count(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the total entry count for a Wufoo form.

    config:
      subdomain — Wufoo account subdomain (required)
      api_key   — Wufoo API key (required)
      form_hash — unique form identifier (required)
    """
    merged = {**config, **input_data}
    subdomain = merged.get("subdomain", "")
    api_key = merged.get("api_key", "")
    form_hash = merged.get("form_hash")
    if not form_hash:
        raise ValueError("form_hash is required for wufoo.get_entry_count")

    auth = httpx.BasicAuth(api_key, "footastic")

    async with httpx.AsyncClient(base_url=_wufoo_base(subdomain), timeout=30) as client:
        r = await client.get(f"/forms/{form_hash}/entries/count.json", auth=auth)
        r.raise_for_status()
        data = r.json()

    entry_count = data.get("EntryCount", 0)
    log.info("wufoo.get_entry_count", form_hash=form_hash, entry_count=entry_count)
    return {"entry_count": entry_count, "form_hash": form_hash}


@register_node("wufoo.submit_entry")
async def wufoo_submit_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Submit a new entry to a Wufoo form.

    config:
      subdomain — Wufoo account subdomain (required)
      api_key   — Wufoo API key (required)
      form_hash — unique form identifier (required)
      fields    — dict mapping field IDs (e.g. "Field1") to values (required)
    """
    merged = {**config, **input_data}
    subdomain = merged.get("subdomain", "")
    api_key = merged.get("api_key", "")
    form_hash = merged.get("form_hash")
    fields = merged.get("fields", {})
    if not form_hash:
        raise ValueError("form_hash is required for wufoo.submit_entry")
    if not fields:
        raise ValueError("fields dict is required for wufoo.submit_entry")

    auth = httpx.BasicAuth(api_key, "footastic")

    async with httpx.AsyncClient(base_url=_wufoo_base(subdomain), timeout=30) as client:
        r = await client.post(
            f"/forms/{form_hash}/entries.json",
            auth=auth,
            data=fields,
        )
        r.raise_for_status()
        data = r.json()

    success = data.get("Success", 0)
    log.info("wufoo.submit_entry", form_hash=form_hash, success=success)
    return {"success": bool(success), "response": data, "form_hash": form_hash}
