"""Microsoft Excel 365 integration — workbooks, worksheets, ranges, and tables via Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("excel_365.list_workbooks")
async def excel_365_list_workbooks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Excel workbooks (.xlsx) in the user's OneDrive.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      top          — maximum number of items to return (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {"$filter": "file/mimeType eq 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"}
    if merged.get("top"):
        params["$top"] = merged["top"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/me/drive/root/search(q='.xlsx')", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    workbooks = data.get("value", [])
    log.info("excel_365.list_workbooks", count=len(workbooks))
    return {"workbooks": workbooks, "count": len(workbooks)}


@register_node("excel_365.get_worksheet")
async def excel_365_get_worksheet(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get worksheets in an Excel workbook.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      item_id      — OneDrive item ID of the workbook (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    item_id = merged.get("item_id")
    if not item_id:
        raise ValueError("item_id is required for excel_365.get_worksheet")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/me/drive/items/{item_id}/workbook/worksheets",
            headers=_graph_headers(access_token),
        )
        r.raise_for_status()
        data = r.json()

    worksheets = data.get("value", [])
    log.info("excel_365.get_worksheet", item_id=item_id, count=len(worksheets))
    return {"worksheets": worksheets, "count": len(worksheets)}


@register_node("excel_365.get_range")
async def excel_365_get_range(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get values from a range in an Excel worksheet.

    config/input_data:
      access_token   — Microsoft Graph OAuth2 bearer token (required)
      item_id        — OneDrive item ID of the workbook (required)
      worksheet_name — name of the worksheet (required)
      address        — cell range address, e.g. "A1:C10" (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    item_id = merged.get("item_id")
    worksheet_name = merged.get("worksheet_name")
    address = merged.get("address")
    if not item_id:
        raise ValueError("item_id is required for excel_365.get_range")
    if not worksheet_name:
        raise ValueError("worksheet_name is required for excel_365.get_range")
    if not address:
        raise ValueError("address is required for excel_365.get_range")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/me/drive/items/{item_id}/workbook/worksheets/{worksheet_name}/range(address='{address}')",
            headers=_graph_headers(access_token),
        )
        r.raise_for_status()
        range_data = r.json()

    log.info("excel_365.get_range", item_id=item_id, worksheet=worksheet_name, address=address)
    return {"range": range_data, "values": range_data.get("values", [])}


@register_node("excel_365.update_range")
async def excel_365_update_range(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update values in a range in an Excel worksheet.

    config/input_data:
      access_token   — Microsoft Graph OAuth2 bearer token (required)
      item_id        — OneDrive item ID of the workbook (required)
      worksheet_name — name of the worksheet (required)
      address        — cell range address, e.g. "A1:C3" (required)
      values         — 2D array of values to set (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    item_id = merged.get("item_id")
    worksheet_name = merged.get("worksheet_name")
    address = merged.get("address")
    values = merged.get("values")
    if not item_id:
        raise ValueError("item_id is required for excel_365.update_range")
    if not worksheet_name:
        raise ValueError("worksheet_name is required for excel_365.update_range")
    if not address:
        raise ValueError("address is required for excel_365.update_range")
    if values is None:
        raise ValueError("values is required for excel_365.update_range")

    payload = {"values": values}

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(
            f"/me/drive/items/{item_id}/workbook/worksheets/{worksheet_name}/range(address='{address}')",
            headers=_graph_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        range_data = r.json()

    log.info("excel_365.update_range", item_id=item_id, worksheet=worksheet_name, address=address)
    return {"range": range_data, "address": address, "updated": True}


@register_node("excel_365.create_table")
async def excel_365_create_table(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a table in an Excel worksheet.

    config/input_data:
      access_token   — Microsoft Graph OAuth2 bearer token (required)
      item_id        — OneDrive item ID of the workbook (required)
      worksheet_name — name of the worksheet (required)
      address        — range for the table, e.g. "A1:D5" (required)
      has_headers    — whether the range has headers (optional, default True)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    item_id = merged.get("item_id")
    worksheet_name = merged.get("worksheet_name")
    address = merged.get("address")
    if not item_id:
        raise ValueError("item_id is required for excel_365.create_table")
    if not worksheet_name:
        raise ValueError("worksheet_name is required for excel_365.create_table")
    if not address:
        raise ValueError("address is required for excel_365.create_table")

    payload = {"address": address, "hasHeaders": merged.get("has_headers", True)}

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post(
            f"/me/drive/items/{item_id}/workbook/worksheets/{worksheet_name}/tables/add",
            headers=_graph_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        table = r.json()

    log.info("excel_365.create_table", item_id=item_id, worksheet=worksheet_name, table_id=table.get("id"))
    return {"table": table, "table_id": table.get("id")}


@register_node("excel_365.get_table_rows")
async def excel_365_get_table_rows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get rows from an Excel table.

    config/input_data:
      access_token   — Microsoft Graph OAuth2 bearer token (required)
      item_id        — OneDrive item ID of the workbook (required)
      worksheet_name — name of the worksheet (required)
      table_name     — name or ID of the table (required)
      top            — maximum number of rows to return (optional)
      skip           — number of rows to skip (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    item_id = merged.get("item_id")
    worksheet_name = merged.get("worksheet_name")
    table_name = merged.get("table_name")
    if not item_id:
        raise ValueError("item_id is required for excel_365.get_table_rows")
    if not worksheet_name:
        raise ValueError("worksheet_name is required for excel_365.get_table_rows")
    if not table_name:
        raise ValueError("table_name is required for excel_365.get_table_rows")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("skip"):
        params["$skip"] = merged["skip"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/me/drive/items/{item_id}/workbook/worksheets/{worksheet_name}/tables/{table_name}/rows",
            headers=_graph_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    rows = data.get("value", [])
    log.info("excel_365.get_table_rows", item_id=item_id, table=table_name, count=len(rows))
    return {"rows": rows, "count": len(rows)}
