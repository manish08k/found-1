"""Smartsheet collaboration integration — sheets, rows, and columns."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SMARTSHEET_BASE = "https://api.smartsheet.com/2.0"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("smartsheet.list_sheets")
async def smartsheet_list_sheets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Smartsheet sheets accessible to the user.

    config:
      api_key — Smartsheet API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for smartsheet.list_sheets")

    async with httpx.AsyncClient(base_url=SMARTSHEET_BASE, timeout=30) as client:
        r = await client.get("/sheets", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    sheets = data.get("data", [])
    total = data.get("totalCount", len(sheets))
    log.info("smartsheet.list_sheets", count=len(sheets))
    return {"sheets": sheets, "count": len(sheets), "total": total}


@register_node("smartsheet.get_sheet")
async def smartsheet_get_sheet(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a Smartsheet sheet with all rows and columns.

    config/input_data:
      api_key  — Smartsheet API key (required)
      sheet_id — sheet ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for smartsheet.get_sheet")

    sheet_id = config.get("sheet_id") or input_data.get("sheet_id")
    if not sheet_id:
        raise ValueError("sheet_id is required for smartsheet.get_sheet")

    async with httpx.AsyncClient(base_url=SMARTSHEET_BASE, timeout=30) as client:
        r = await client.get(f"/sheets/{sheet_id}", headers=_headers(api_key))
        r.raise_for_status()
        sheet = r.json()

    log.info("smartsheet.get_sheet", sheet_id=sheet_id, name=sheet.get("name"))
    return {"sheet": sheet}


@register_node("smartsheet.add_row")
async def smartsheet_add_row(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a row to a Smartsheet sheet.

    config/input_data:
      api_key  — Smartsheet API key (required)
      sheet_id — sheet ID (required)
      col_id   — column ID to set a value on (required)
      value    — cell value (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for smartsheet.add_row")

    sheet_id = config.get("sheet_id") or input_data.get("sheet_id")
    col_id = config.get("col_id") or input_data.get("col_id")
    value = config.get("value") or input_data.get("value")
    if not sheet_id or not col_id:
        raise ValueError("sheet_id and col_id are required for smartsheet.add_row")

    payload = {"toBottom": True, "cells": [{"columnId": col_id, "value": value}]}

    async with httpx.AsyncClient(base_url=SMARTSHEET_BASE, timeout=30) as client:
        r = await client.post(
            f"/sheets/{sheet_id}/rows",
            json=payload,
            headers=_headers(api_key),
        )
        r.raise_for_status()
        data = r.json()

    result = data.get("result", [{}])
    row_id = result[0].get("id") if result else None
    log.info("smartsheet.add_row", sheet_id=sheet_id, row_id=row_id)
    return {"result": data, "row_id": row_id}


@register_node("smartsheet.list_columns")
async def smartsheet_list_columns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List columns in a Smartsheet sheet.

    config:
      api_key  — Smartsheet API key (required)
      sheet_id — sheet ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for smartsheet.list_columns")

    sheet_id = config.get("sheet_id") or input_data.get("sheet_id")
    if not sheet_id:
        raise ValueError("sheet_id is required for smartsheet.list_columns")

    async with httpx.AsyncClient(base_url=SMARTSHEET_BASE, timeout=30) as client:
        r = await client.get(f"/sheets/{sheet_id}/columns", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    columns = data.get("data", [])
    log.info("smartsheet.list_columns", sheet_id=sheet_id, count=len(columns))
    return {"columns": columns, "count": len(columns)}
