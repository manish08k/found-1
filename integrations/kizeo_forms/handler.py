"""Kizeo Forms integration — mobile form management and data export."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

KIZEO_BASE = "https://www.kizeoforms.com/rest/v3"


def _kizeo_headers(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}


@register_node("kizeo_forms.list_forms")
async def kizeo_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all forms available in the Kizeo Forms account.

    config:
      token — Kizeo Forms API token (required)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")

    async with httpx.AsyncClient(base_url=KIZEO_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_kizeo_headers(token))
        r.raise_for_status()
        data = r.json()

    forms = data.get("forms", data) if isinstance(data, dict) else data
    log.info("kizeo_forms.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("kizeo_forms.get_data")
async def kizeo_get_data(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get data records for a specific Kizeo Forms form.

    config:
      token   — Kizeo Forms API token (required)
      form_id — form ID to fetch data for (required)
      start   — start index for pagination (optional)
      limit   — max records to return (optional)
      order   — sort order field (optional)
      filter  — filter expression (optional)
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("form_id is required for kizeo_forms.get_data")

    params = {}
    if merged.get("start") is not None:
        params["start"] = merged["start"]
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]
    if merged.get("order"):
        params["order"] = merged["order"]
    if merged.get("filter"):
        params["filter"] = merged["filter"]

    async with httpx.AsyncClient(base_url=KIZEO_BASE, timeout=30) as client:
        r = await client.get(
            f"/forms/{form_id}/data",
            headers=_kizeo_headers(token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    records = data.get("data", data) if isinstance(data, dict) else data
    log.info("kizeo_forms.get_data", form_id=form_id, count=len(records))
    return {"data": records, "form_id": form_id, "count": len(records)}


@register_node("kizeo_forms.export_data")
async def kizeo_export_data(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Export data from a Kizeo Forms form in the requested format.

    config:
      token       — Kizeo Forms API token (required)
      form_id     — form ID to export data from (required)
      data_ids    — list of data record IDs to export (required)
      export_type — export format: "excel", "pdf", "csv" (optional, default "excel")
    """
    merged = {**config, **input_data}
    token = merged.get("token", "")
    form_id = merged.get("form_id")
    data_ids = merged.get("data_ids")
    export_type = merged.get("export_type", "excel")
    if not form_id:
        raise ValueError("form_id is required for kizeo_forms.export_data")
    if not data_ids:
        raise ValueError("data_ids is required for kizeo_forms.export_data")

    payload = {"data_ids": data_ids if isinstance(data_ids, list) else [data_ids]}

    async with httpx.AsyncClient(base_url=KIZEO_BASE, timeout=60) as client:
        r = await client.post(
            f"/forms/{form_id}/multiple_data/exports/{export_type}",
            headers=_kizeo_headers(token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    log.info("kizeo_forms.export_data", form_id=form_id, export_type=export_type, records=len(payload["data_ids"]))
    return {"export": data, "form_id": form_id, "export_type": export_type}
