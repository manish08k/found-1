"""Cognito Forms integration — form and entry management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

COGNITO_BASE = "https://www.cognitoforms.com/api"


def _cognito_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("cognito_forms.list_forms")
async def cognito_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms in the Cognito Forms account.

    config:
      api_key — Cognito Forms API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    async with httpx.AsyncClient(base_url=COGNITO_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_cognito_headers(api_key))
        r.raise_for_status()
        data = r.json()

    forms = data if isinstance(data, list) else data.get("forms", [])
    log.info("cognito_forms.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("cognito_forms.get_entries")
async def cognito_get_entries(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get entries (submissions) for a specific Cognito Forms form.

    config:
      api_key — Cognito Forms API key (required)
      form_id — form ID to fetch entries for (required)
      filter  — OData filter expression (optional)
      top     — max number of entries to return (optional)
      skip    — number of entries to skip for pagination (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for cognito_forms.get_entries")

    params = {}
    if merged.get("filter"):
        params["$filter"] = merged["filter"]
    if merged.get("top") is not None:
        params["$top"] = merged["top"]
    if merged.get("skip") is not None:
        params["$skip"] = merged["skip"]

    async with httpx.AsyncClient(base_url=COGNITO_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}/entries",
            headers=_cognito_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    entries = data if isinstance(data, list) else data.get("entries", [])
    log.info("cognito_forms.get_entries", form_id=form_id, count=len(entries))
    return {"entries": entries, "form_id": form_id, "count": len(entries)}


@register_node("cognito_forms.create_entry")
async def cognito_create_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new entry in a Cognito Forms form.

    config:
      api_key    — Cognito Forms API key (required)
      form_id    — form ID to submit entry to (required)
      entry_data — dict of field names to values (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    entry_data = merged.get("entry_data")
    if not form_id:
        raise ValueError("form_id is required for cognito_forms.create_entry")
    if not entry_data:
        raise ValueError("entry_data is required for cognito_forms.create_entry")

    async with httpx.AsyncClient(base_url=COGNITO_BASE, timeout=30) as client:
        r = await client.post(
            f"/forms/{form_id}/entries",
            headers=_cognito_headers(api_key),
            json=entry_data,
        )
        r.raise_for_status()
        entry = r.json()

    entry_id = entry.get("Id") or entry.get("id") if isinstance(entry, dict) else None
    log.info("cognito_forms.create_entry", form_id=form_id, entry_id=entry_id)
    return {"entry": entry, "form_id": form_id, "entry_id": entry_id}


@register_node("cognito_forms.update_entry")
async def cognito_update_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing entry in a Cognito Forms form.

    config:
      api_key    — Cognito Forms API key (required)
      form_id    — form ID containing the entry (required)
      entry_id   — entry ID to update (required)
      entry_data — dict of field names to updated values (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    entry_id = merged.get("entry_id")
    entry_data = merged.get("entry_data")
    if not form_id:
        raise ValueError("form_id is required for cognito_forms.update_entry")
    if not entry_id:
        raise ValueError("entry_id is required for cognito_forms.update_entry")
    if not entry_data:
        raise ValueError("entry_data is required for cognito_forms.update_entry")

    async with httpx.AsyncClient(base_url=COGNITO_BASE, timeout=30) as client:
        r = await client.put(
            f"/forms/{form_id}/entries/{entry_id}",
            headers=_cognito_headers(api_key),
            json=entry_data,
        )
        r.raise_for_status()
        entry = r.json()

    log.info("cognito_forms.update_entry", form_id=form_id, entry_id=entry_id)
    return {"entry": entry, "form_id": form_id, "entry_id": entry_id}


@register_node("cognito_forms.delete_entry")
async def cognito_delete_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an entry from a Cognito Forms form.

    config:
      api_key  — Cognito Forms API key (required)
      form_id  — form ID containing the entry (required)
      entry_id — entry ID to delete (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    form_id = merged.get("form_id")
    entry_id = merged.get("entry_id")
    if not form_id:
        raise ValueError("form_id is required for cognito_forms.delete_entry")
    if not entry_id:
        raise ValueError("entry_id is required for cognito_forms.delete_entry")

    async with httpx.AsyncClient(base_url=COGNITO_BASE, timeout=30) as client:
        r = await client.delete(
            f"/forms/{form_id}/entries/{entry_id}",
            headers=_cognito_headers(api_key),
        )
        r.raise_for_status()

    log.info("cognito_forms.delete_entry", form_id=form_id, entry_id=entry_id)
    return {"deleted": True, "form_id": form_id, "entry_id": entry_id}
