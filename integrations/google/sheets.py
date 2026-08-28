"""Google Sheets integration — full CRUD + polling."""
import structlog
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from core.execution_engine import register_node
from triggers.engine import register_poller
from oauth.flow import get_access_token
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)


async def _sheets_service(credential_id: str, db):
    from sqlalchemy import select
    from storage.models import OAuthCredential
    result = await db.execute(select(OAuthCredential).where(OAuthCredential.id == credential_id))
    cred_row = result.scalar_one()
    token_data = decrypt_credential(cred_row.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)

    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


@register_node("sheets.read_rows")
async def sheets_read_rows(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _sheets_service(credential_id, db)
    spreadsheet_id = config.get("spreadsheet_id") or input_data.get("spreadsheet_id")
    range_ = config.get("range", "Sheet1")
    value_render = config.get("value_render", "FORMATTED_VALUE")

    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_,
        valueRenderOption=value_render,
    ).execute()

    values = result.get("values", [])
    headers = values[0] if values else []
    rows = [dict(zip(headers, row)) for row in values[1:]] if len(values) > 1 else []
    return {"rows": rows, "headers": headers, "raw": values}


@register_node("sheets.append_row")
async def sheets_append_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _sheets_service(credential_id, db)
    spreadsheet_id = config.get("spreadsheet_id") or input_data.get("spreadsheet_id")
    range_ = config.get("range", "Sheet1")
    row_data = config.get("row") or input_data.get("row", [])

    if isinstance(row_data, dict):
        row_data = list(row_data.values())

    body = {"values": [row_data]}
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()

    return {
        "updated_range": result.get("updates", {}).get("updatedRange"),
        "updated_rows": result.get("updates", {}).get("updatedRows"),
    }


@register_node("sheets.update_row")
async def sheets_update_row(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _sheets_service(credential_id, db)
    spreadsheet_id = config.get("spreadsheet_id") or input_data.get("spreadsheet_id")
    range_ = config.get("range") or input_data.get("range")
    row_data = config.get("row") or input_data.get("row", [])

    if isinstance(row_data, dict):
        row_data = list(row_data.values())

    body = {"values": [row_data]}
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()

    return {"updated_cells": result.get("updatedCells"), "updated_range": result.get("updatedRange")}


@register_node("sheets.clear_range")
async def sheets_clear_range(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _sheets_service(credential_id, db)
    spreadsheet_id = config.get("spreadsheet_id") or input_data.get("spreadsheet_id")
    range_ = config.get("range") or input_data.get("range")

    result = service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_,
        body={},
    ).execute()
    return {"cleared_range": result.get("clearedRange")}


@register_node("sheets.create_spreadsheet")
async def sheets_create_spreadsheet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _sheets_service(credential_id, db)
    title = config.get("title") or input_data.get("title", "New Spreadsheet")
    sheets = config.get("sheets", [{"properties": {"title": "Sheet1"}}])

    body = {"properties": {"title": title}, "sheets": sheets}
    result = service.spreadsheets().create(body=body).execute()
    return {
        "spreadsheet_id": result["spreadsheetId"],
        "url": result["spreadsheetUrl"],
    }


@register_node("sheets.get_sheet_info")
async def sheets_get_sheet_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _sheets_service(credential_id, db)
    spreadsheet_id = config.get("spreadsheet_id") or input_data.get("spreadsheet_id")

    result = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return {
        "title": result["properties"]["title"],
        "sheets": [s["properties"]["title"] for s in result.get("sheets", [])],
        "spreadsheet_id": spreadsheet_id,
    }


@register_node("sheets.batch_update")
async def sheets_batch_update(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _sheets_service(credential_id, db)
    spreadsheet_id = config.get("spreadsheet_id") or input_data.get("spreadsheet_id")
    data = config.get("data") or input_data.get("data", [])
    # data: [{"range": "Sheet1!A1", "values": [[...]]}]

    body = {"valueInputOption": "USER_ENTERED", "data": data}
    result = service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body,
    ).execute()
    return {"total_updated_cells": result.get("totalUpdatedCells")}


# ─── Polling: new row added ───────────────────────────────────────────────────

_sheets_row_counts: dict[str, int] = {}


@register_poller("sheets", "new_row")
async def poll_sheets_new_row(config: dict, credential_id: str, db) -> list[dict]:
    service = await _sheets_service(credential_id, db)
    spreadsheet_id = config.get("spreadsheet_id")
    range_ = config.get("range", "Sheet1")

    if not spreadsheet_id:
        return []

    key = f"{credential_id}:{spreadsheet_id}:{range_}"

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_,
        ).execute()
        values = result.get("values", [])
        current_count = len(values)
        last_count = _sheets_row_counts.get(key, current_count)

        new_items = []
        if current_count > last_count:
            headers = values[0] if values else []
            for row in values[last_count:]:
                new_items.append(dict(zip(headers, row)))

        _sheets_row_counts[key] = current_count
        return new_items
    except Exception as e:
        log.error("sheets_poll_error", error=str(e))
        return []
