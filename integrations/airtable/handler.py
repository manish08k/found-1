"""Airtable integration — records, tables, views, webhooks + polling."""
import structlog
import httpx

from core.execution_engine import register_node
from triggers.engine import register_poller
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)

AT_BASE = "https://api.airtable.com/v0"
AT_META_BASE = "https://api.airtable.com/v0/meta"


async def _at(credential_id: str, db) -> httpx.AsyncClient:
    token = await get_access_token(credential_id, db)
    return httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )


@register_node("airtable.list_records")
async def at_list_records(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_id = config.get("base_id") or input_data.get("base_id")
    table = config.get("table") or input_data.get("table")
    view = config.get("view")
    filter_formula = config.get("filter_formula")
    max_records = config.get("max_records", 100)
    fields = config.get("fields", [])

    params = {"maxRecords": max_records}
    if view:
        params["view"] = view
    if filter_formula:
        params["filterByFormula"] = filter_formula
    if fields:
        for f in fields:
            params.setdefault("fields[]", []).append(f)

    records = []
    offset = None
    async with await _at(credential_id, db) as client:
        while True:
            if offset:
                params["offset"] = offset
            r = await client.get(f"{AT_BASE}/{base_id}/{table}", params=params)
            r.raise_for_status()
            data = r.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break

    return {"records": records, "count": len(records)}


@register_node("airtable.create_record")
async def at_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_id = config.get("base_id") or input_data.get("base_id")
    table = config.get("table") or input_data.get("table")
    fields = config.get("fields") or input_data.get("fields", {})
    typecast = config.get("typecast", False)

    async with await _at(credential_id, db) as client:
        r = await client.post(f"{AT_BASE}/{base_id}/{table}",
                              json={"fields": fields, "typecast": typecast})
        r.raise_for_status()
        data = r.json()
    return {"record_id": data["id"], "fields": data["fields"]}


@register_node("airtable.update_record")
async def at_update_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_id = config.get("base_id") or input_data.get("base_id")
    table = config.get("table") or input_data.get("table")
    record_id = config.get("record_id") or input_data.get("record_id")
    fields = config.get("fields") or input_data.get("fields", {})
    typecast = config.get("typecast", False)

    async with await _at(credential_id, db) as client:
        r = await client.patch(f"{AT_BASE}/{base_id}/{table}/{record_id}",
                               json={"fields": fields, "typecast": typecast})
        r.raise_for_status()
        data = r.json()
    return {"record_id": data["id"], "fields": data["fields"]}


@register_node("airtable.delete_record")
async def at_delete_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_id = config.get("base_id") or input_data.get("base_id")
    table = config.get("table") or input_data.get("table")
    record_id = config.get("record_id") or input_data.get("record_id")

    async with await _at(credential_id, db) as client:
        r = await client.delete(f"{AT_BASE}/{base_id}/{table}/{record_id}")
        r.raise_for_status()
        data = r.json()
    return {"deleted": data.get("deleted"), "record_id": record_id}


@register_node("airtable.upsert_record")
async def at_upsert_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_id = config.get("base_id") or input_data.get("base_id")
    table = config.get("table") or input_data.get("table")
    fields = config.get("fields") or input_data.get("fields", {})
    fields_to_merge_on = config.get("fields_to_merge_on") or input_data.get("fields_to_merge_on", [])

    async with await _at(credential_id, db) as client:
        r = await client.patch(f"{AT_BASE}/{base_id}/{table}",
                               json={"performUpsert": {"fieldsToMergeOn": fields_to_merge_on},
                                     "records": [{"fields": fields}]})
        r.raise_for_status()
        data = r.json()
    records = data.get("records", [{}])
    return {"record_id": records[0].get("id"), "created": len(data.get("createdRecords", [])) > 0}


@register_node("airtable.list_bases")
async def at_list_bases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _at(credential_id, db) as client:
        r = await client.get(f"{AT_META_BASE}/bases")
        r.raise_for_status()
        data = r.json()
    return {"bases": [{"id": b["id"], "name": b["name"]} for b in data.get("bases", [])]}


@register_node("airtable.get_table_schema")
async def at_get_schema(config: dict, input_data: dict, credential_id: str, db) -> dict:
    base_id = config.get("base_id") or input_data.get("base_id")

    async with await _at(credential_id, db) as client:
        r = await client.get(f"{AT_META_BASE}/bases/{base_id}/tables")
        r.raise_for_status()
        data = r.json()
    return {"tables": data.get("tables", [])}


# ─── Polling ──────────────────────────────────────────────────────────────────

_at_seen: dict[str, set] = {}


@register_poller("airtable", "new_record")
async def poll_airtable_new_record(config: dict, credential_id: str, db) -> list[dict]:
    base_id = config.get("base_id")
    table = config.get("table")
    key = f"{credential_id}:{base_id}:{table}"
    if key not in _at_seen:
        _at_seen[key] = set()

    try:
        async with await _at(credential_id, db) as client:
            r = await client.get(f"{AT_BASE}/{base_id}/{table}",
                                 params={"maxRecords": 20, "sort[0][field]": "Created",
                                         "sort[0][direction]": "desc"})
            r.raise_for_status()
            data = r.json()

        new_items = []
        for rec in data.get("records", []):
            if rec["id"] not in _at_seen[key]:
                new_items.append(rec)
                _at_seen[key].add(rec["id"])
        return new_items
    except Exception as e:
        log.error("airtable_poll_error", error=str(e))
        return []
