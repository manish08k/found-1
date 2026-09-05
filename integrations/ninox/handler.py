"""Ninox database integration — records and tables."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

NINOX_BASE = "https://api.ninox.com/v1"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("ninox.list_records")
async def ninox_list_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List records from a Ninox database table.

    config:
      api_key  — Ninox API key (required)
      team_id  — Ninox team ID (required)
      db_id    — database ID (required)
      table_id — table ID (required)
      per_page — records per page (default 25)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for ninox.list_records")

    team_id = config.get("team_id") or input_data.get("team_id")
    db_id = config.get("db_id") or input_data.get("db_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    if not team_id or not db_id or not table_id:
        raise ValueError("team_id, db_id, and table_id are required for ninox.list_records")

    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=NINOX_BASE, timeout=30) as client:
        r = await client.get(
            f"/teams/{team_id}/databases/{db_id}/tables/{table_id}/records",
            params={"perPage": per_page},
            headers=_headers(api_key),
        )
        r.raise_for_status()
        records = r.json()

    log.info("ninox.list_records", team_id=team_id, db_id=db_id, table_id=table_id, count=len(records))
    return {"records": records, "count": len(records)}


@register_node("ninox.create_record")
async def ninox_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a record in a Ninox table.

    config/input_data:
      api_key  — Ninox API key (required)
      team_id  — Ninox team ID (required)
      db_id    — database ID (required)
      table_id — table ID (required)
      fields   — dict of {field_id: value} pairs (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for ninox.create_record")

    team_id = config.get("team_id") or input_data.get("team_id")
    db_id = config.get("db_id") or input_data.get("db_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    if not team_id or not db_id or not table_id:
        raise ValueError("team_id, db_id, and table_id are required for ninox.create_record")

    fields = config.get("fields") or input_data.get("fields") or {}
    payload = {"fields": fields}

    async with httpx.AsyncClient(base_url=NINOX_BASE, timeout=30) as client:
        r = await client.post(
            f"/teams/{team_id}/databases/{db_id}/tables/{table_id}/records",
            json=payload,
            headers=_headers(api_key),
        )
        r.raise_for_status()
        record = r.json()

    log.info("ninox.create_record", team_id=team_id, table_id=table_id)
    return {"record": record}


@register_node("ninox.list_tables")
async def ninox_list_tables(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List tables in a Ninox database.

    config:
      api_key — Ninox API key (required)
      team_id — Ninox team ID (required)
      db_id   — database ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for ninox.list_tables")

    team_id = config.get("team_id") or input_data.get("team_id")
    db_id = config.get("db_id") or input_data.get("db_id")
    if not team_id or not db_id:
        raise ValueError("team_id and db_id are required for ninox.list_tables")

    async with httpx.AsyncClient(base_url=NINOX_BASE, timeout=30) as client:
        r = await client.get(
            f"/teams/{team_id}/databases/{db_id}/tables",
            headers=_headers(api_key),
        )
        r.raise_for_status()
        tables = r.json()

    log.info("ninox.list_tables", team_id=team_id, db_id=db_id, count=len(tables))
    return {"tables": tables, "count": len(tables)}
