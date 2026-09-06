"""Gravity Forms integration — WordPress form and entry management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _gf_auth(consumer_key: str, consumer_secret: str) -> tuple:
    return (consumer_key, consumer_secret)


@register_node("gravityforms.list_forms")
async def gravityforms_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Gravity Forms on a WordPress site.

    config:
      site_url         — WordPress site URL (required, e.g. "https://example.com")
      consumer_key     — Gravity Forms REST API consumer key (required)
      consumer_secret  — Gravity Forms REST API consumer secret (required)
      active           — filter by active status (optional, true/false)
      trash            — include trashed forms (optional, true/false)
    """
    merged = {**config, **input_data}
    site_url = merged.get("site_url", "").rstrip("/")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    if not site_url:
        raise ValueError("site_url is required for gravityforms.list_forms")

    params = {}
    if merged.get("active") is not None:
        params["active"] = str(merged["active"]).lower()
    if merged.get("trash") is not None:
        params["trash"] = str(merged["trash"]).lower()

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{site_url}/wp-json/gf/v2/forms",
            auth=_gf_auth(consumer_key, consumer_secret),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    forms = data if isinstance(data, list) else data.get("forms", [])
    log.info("gravityforms.list_forms", site_url=site_url, count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("gravityforms.get_entries")
async def gravityforms_get_entries(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get entries for a specific Gravity Forms form.

    config:
      site_url        — WordPress site URL (required)
      consumer_key    — Gravity Forms REST API consumer key (required)
      consumer_secret — Gravity Forms REST API consumer secret (required)
      form_id         — form ID to fetch entries for (required)
      page_size       — number of entries per page (optional)
      current_page    — page number (optional)
      search          — JSON search criteria (optional)
    """
    merged = {**config, **input_data}
    site_url = merged.get("site_url", "").rstrip("/")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    form_id = merged.get("form_id")
    if not site_url:
        raise ValueError("site_url is required for gravityforms.get_entries")
    if not form_id:
        raise ValueError("form_id is required for gravityforms.get_entries")

    params = {}
    if merged.get("page_size") is not None:
        params["paging[page_size]"] = merged["page_size"]
    if merged.get("current_page") is not None:
        params["paging[current_page]"] = merged["current_page"]
    if merged.get("search"):
        params["search"] = merged["search"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{site_url}/wp-json/gf/v2/forms/{form_id}/entries",
            auth=_gf_auth(consumer_key, consumer_secret),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    entries = data.get("entries", data) if isinstance(data, dict) else data
    total_count = data.get("total_count") if isinstance(data, dict) else len(entries)
    log.info("gravityforms.get_entries", form_id=form_id, count=len(entries))
    return {"entries": entries, "form_id": form_id, "count": len(entries), "total_count": total_count}


@register_node("gravityforms.create_entry")
async def gravityforms_create_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new entry for a Gravity Forms form.

    config:
      site_url        — WordPress site URL (required)
      consumer_key    — Gravity Forms REST API consumer key (required)
      consumer_secret — Gravity Forms REST API consumer secret (required)
      form_id         — form ID to submit entry to (required)
      entry_data      — dict of field IDs to values (required)
    """
    merged = {**config, **input_data}
    site_url = merged.get("site_url", "").rstrip("/")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    form_id = merged.get("form_id")
    entry_data = merged.get("entry_data")
    if not site_url:
        raise ValueError("site_url is required for gravityforms.create_entry")
    if not form_id:
        raise ValueError("form_id is required for gravityforms.create_entry")
    if not entry_data:
        raise ValueError("entry_data is required for gravityforms.create_entry")

    payload = {"form_id": form_id, **entry_data}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{site_url}/wp-json/gf/v2/entries",
            auth=_gf_auth(consumer_key, consumer_secret),
            json=payload,
        )
        r.raise_for_status()
        entry = r.json()

    entry_id = entry.get("id") if isinstance(entry, dict) else None
    log.info("gravityforms.create_entry", form_id=form_id, entry_id=entry_id)
    return {"entry": entry, "form_id": form_id, "entry_id": entry_id}


@register_node("gravityforms.update_entry")
async def gravityforms_update_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing Gravity Forms entry.

    config:
      site_url        — WordPress site URL (required)
      consumer_key    — Gravity Forms REST API consumer key (required)
      consumer_secret — Gravity Forms REST API consumer secret (required)
      entry_id        — entry ID to update (required)
      entry_data      — dict of field IDs to updated values (required)
    """
    merged = {**config, **input_data}
    site_url = merged.get("site_url", "").rstrip("/")
    consumer_key = merged.get("consumer_key", "")
    consumer_secret = merged.get("consumer_secret", "")
    entry_id = merged.get("entry_id")
    entry_data = merged.get("entry_data")
    if not site_url:
        raise ValueError("site_url is required for gravityforms.update_entry")
    if not entry_id:
        raise ValueError("entry_id is required for gravityforms.update_entry")
    if not entry_data:
        raise ValueError("entry_data is required for gravityforms.update_entry")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(
            f"{site_url}/wp-json/gf/v2/entries/{entry_id}",
            auth=_gf_auth(consumer_key, consumer_secret),
            json=entry_data,
        )
        r.raise_for_status()
        entry = r.json()

    log.info("gravityforms.update_entry", entry_id=entry_id)
    return {"entry": entry, "entry_id": entry_id}
