"""Google Sheets (Activepieces integration) — handler for google_sheets_ap integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://sheets.googleapis.com/v4"


@register_node("google_sheets_ap.get_values")
async def google_sheets_ap_get_values(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get cell values.

    config/input_data:
      api_key — API key or token (required)
      spreadsheet_id — (required)
      range — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    spreadsheet_id = merged.get("spreadsheet_id") or ""
    range = merged.get("range") or ""
    if not spreadsheet_id or not range:
        raise ValueError("spreadsheet_id, range required for google_sheets_ap.get_values")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/spreadsheets/{spreadsheet_id}/values/{range}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("google_sheets_ap.get_values")
    return {"data": data}

@register_node("google_sheets_ap.update_values")
async def google_sheets_ap_update_values(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update cell values.

    config/input_data:
      api_key — API key or token (required)
      spreadsheet_id — (required)
      range — (required)
      values — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    spreadsheet_id = merged.get("spreadsheet_id") or ""
    range = merged.get("range") or ""
    values = merged.get("values") or ""
    if not spreadsheet_id or not range or not values:
        raise ValueError("spreadsheet_id, range, values required for google_sheets_ap.update_values")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(f"{BASE_URL}/spreadsheets/{spreadsheet_id}/values/{range}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("google_sheets_ap.update_values")
    return {"data": data}

@register_node("google_sheets_ap.append_values")
async def google_sheets_ap_append_values(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Append rows.

    config/input_data:
      api_key — API key or token (required)
      spreadsheet_id — (required)
      range — (required)
      values — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    spreadsheet_id = merged.get("spreadsheet_id") or ""
    range = merged.get("range") or ""
    values = merged.get("values") or ""
    if not spreadsheet_id or not range or not values:
        raise ValueError("spreadsheet_id, range, values required for google_sheets_ap.append_values")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/spreadsheets/{spreadsheet_id}/values/{range}:append", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("google_sheets_ap.append_values")
    return {"data": data}

@register_node("google_sheets_ap.get_spreadsheet")
async def google_sheets_ap_get_spreadsheet(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get spreadsheet metadata.

    config/input_data:
      api_key — API key or token (required)
      spreadsheet_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    spreadsheet_id = merged.get("spreadsheet_id") or ""
    if not spreadsheet_id:
        raise ValueError("spreadsheet_id required for google_sheets_ap.get_spreadsheet")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/spreadsheets/{spreadsheet_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("google_sheets_ap.get_spreadsheet")
    return {"data": data}
