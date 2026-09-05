"""Grist integration — documents, tables, and records."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

GRIST_BASE = "https://docs.getgrist.com/api/"


async def _grist_client(credential_id: str, db) -> httpx.AsyncClient:
    """Build an authenticated Grist AsyncClient.

    Credential fields:
      api_key   — Grist API key
      base_url  — optional custom Grist instance URL (for self-hosted)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = creds.get("base_url", GRIST_BASE).rstrip("/") + "/"

    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )


@register_node("grist.list_docs")
async def grist_list_docs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all Grist documents in an org/workspace.

    config:
      org_id       — org ID or 'docs' for personal account (default 'docs')
      workspace_id — specific workspace ID to list docs in (optional)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = creds.get("base_url", GRIST_BASE).rstrip("/") + "/"

    org_id = config.get("org_id") or input_data.get("org_id", "docs")
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        if workspace_id:
            r = await client.get(f"workspaces/{workspace_id}/docs")
        else:
            r = await client.get(f"orgs/{org_id}/workspaces")
            r.raise_for_status()
            workspaces = r.json()
            # Flatten all docs from all workspaces
            docs = []
            for ws in (workspaces if isinstance(workspaces, list) else []):
                docs.extend(ws.get("docs", []))
            log.info("grist.list_docs", org_id=org_id, count=len(docs))
            return {"docs": docs, "count": len(docs), "org_id": org_id}

        r.raise_for_status()
        docs = r.json()

    docs_list = docs if isinstance(docs, list) else docs.get("docs", [])
    log.info("grist.list_docs", workspace_id=workspace_id, count=len(docs_list))
    return {"docs": docs_list, "count": len(docs_list), "workspace_id": workspace_id}


@register_node("grist.list_tables")
async def grist_list_tables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all tables in a Grist document.

    config/input_data:
      doc_id — Grist document ID (required)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = creds.get("base_url", GRIST_BASE).rstrip("/") + "/"

    doc_id = config.get("doc_id") or input_data.get("doc_id")
    if not doc_id:
        raise ValueError("doc_id is required for grist.list_tables")

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get(f"docs/{doc_id}/tables")
        r.raise_for_status()
        data = r.json()

    tables = data.get("tables", []) if isinstance(data, dict) else data
    log.info("grist.list_tables", doc_id=doc_id, count=len(tables))
    return {"tables": tables, "count": len(tables), "doc_id": doc_id}


@register_node("grist.list_records")
async def grist_list_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch records from a Grist table.

    config/input_data:
      doc_id     — Grist document ID (required)
      table_id   — table ID/name (required)
      filter     — JSON filter object, e.g. {"Status": ["Active"]}
      sort       — column name to sort by (prefix - for descending)
      limit      — max records (default 500)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = creds.get("base_url", GRIST_BASE).rstrip("/") + "/"

    doc_id = config.get("doc_id") or input_data.get("doc_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    if not doc_id or not table_id:
        raise ValueError("doc_id and table_id are required for grist.list_records")

    params: dict = {"limit": int(config.get("limit", 500))}
    filter_obj = config.get("filter") or input_data.get("filter")
    sort = config.get("sort") or input_data.get("sort")

    if filter_obj:
        import json as _json
        params["filter"] = _json.dumps(filter_obj) if isinstance(filter_obj, dict) else filter_obj
    if sort:
        params["sort"] = sort

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get(f"docs/{doc_id}/tables/{table_id}/records", params=params)
        r.raise_for_status()
        data = r.json()

    records = data.get("records", [])
    log.info("grist.list_records", doc_id=doc_id, table_id=table_id, count=len(records))
    return {"records": records, "count": len(records), "doc_id": doc_id, "table_id": table_id}


@register_node("grist.add_records")
async def grist_add_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add new records to a Grist table.

    config/input_data:
      doc_id   — Grist document ID (required)
      table_id — table ID/name (required)
      records  — list of field dicts to insert, e.g. [{"Name": "Alice", "Age": 30}]
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = creds.get("base_url", GRIST_BASE).rstrip("/") + "/"

    doc_id = config.get("doc_id") or input_data.get("doc_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    records = config.get("records") or input_data.get("records", [])

    if not doc_id or not table_id:
        raise ValueError("doc_id and table_id are required for grist.add_records")
    if not records:
        raise ValueError("records list cannot be empty for grist.add_records")

    # Grist expects {"records": [{"fields": {...}}, ...]}
    payload = {"records": [{"fields": r} if "fields" not in r else r for r in records]}

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post(f"docs/{doc_id}/tables/{table_id}/records", json=payload)
        r.raise_for_status()
        data = r.json()

    added_ids = [rec.get("id") for rec in data.get("records", [])]
    log.info("grist.add_records", doc_id=doc_id, table_id=table_id, added=len(added_ids))
    return {
        "added_ids": added_ids,
        "count": len(added_ids),
        "doc_id": doc_id,
        "table_id": table_id,
    }


@register_node("grist.update_records")
async def grist_update_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update existing records in a Grist table by record ID.

    config/input_data:
      doc_id   — Grist document ID (required)
      table_id — table ID/name (required)
      records  — list of {id: int, fields: dict} to update
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = creds.get("base_url", GRIST_BASE).rstrip("/") + "/"

    doc_id = config.get("doc_id") or input_data.get("doc_id")
    table_id = config.get("table_id") or input_data.get("table_id")
    records = config.get("records") or input_data.get("records", [])

    if not doc_id or not table_id:
        raise ValueError("doc_id and table_id are required for grist.update_records")
    if not records:
        raise ValueError("records list cannot be empty for grist.update_records")

    # Normalise: each record must have id + fields
    normalised = []
    for rec in records:
        if "id" not in rec:
            raise ValueError(f"Each record must have an 'id' field for grist.update_records, got: {rec}")
        normalised.append({"id": rec["id"], "fields": rec.get("fields", {k: v for k, v in rec.items() if k != "id"})})

    payload = {"records": normalised}

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.patch(f"docs/{doc_id}/tables/{table_id}/records", json=payload)
        r.raise_for_status()

    log.info("grist.update_records", doc_id=doc_id, table_id=table_id, updated=len(normalised))
    return {
        "updated_count": len(normalised),
        "updated_ids": [rec["id"] for rec in normalised],
        "doc_id": doc_id,
        "table_id": table_id,
    }
