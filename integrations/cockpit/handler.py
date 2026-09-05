"""
Cockpit headless CMS integration.

Provides collection entry management and singleton retrieval via the
Cockpit CMS REST API.

Credential fields:
  - base_url : Base URL of the Cockpit instance, e.g. https://cms.example.com
  - api_key  : Cockpit API key (sent as Cockpit-Token header)

Base URL: https://{base_url}/api/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """Returns (client, api_base_url)."""
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    api_key = creds.get("api_key")
    if not base_url:
        raise ValueError("Cockpit credential missing 'base_url'")
    if not api_key:
        raise ValueError("Cockpit credential missing 'api_key'")

    api_base = f"{base_url}/api"
    client = httpx.AsyncClient(
        base_url=api_base,
        headers={
            "Cockpit-Token": api_key,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    return client, api_base


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cockpit API error {r.status_code}: {detail}")


@register_node("cockpit.get_collection_entries")
async def cockpit_get_collection_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch entries from a Cockpit collection.

    Config:
      - collection : Name of the collection (required)
      - limit      : Max number of entries (default 100)
      - skip       : Offset for pagination (default 0)
      - filter     : Optional dict of filter criteria
      - sort       : Optional dict for sorting, e.g. {"_created": -1}
    """
    collection = config.get("collection") or input_data.get("collection")
    if not collection:
        raise ValueError("cockpit.get_collection_entries requires 'collection'")

    limit = int(config.get("limit") or input_data.get("limit", 100))
    skip = int(config.get("skip") or input_data.get("skip", 0))
    filter_val = config.get("filter") or input_data.get("filter")
    sort = config.get("sort") or input_data.get("sort")

    payload: dict = {"limit": limit, "skip": skip}
    if filter_val:
        payload["filter"] = filter_val
    if sort:
        payload["sort"] = sort

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post(f"/collections/get/{collection}", json=payload)
        _raise_for_status(r)
        data = r.json()

    entries = data.get("entries", data) if isinstance(data, dict) else data
    total = data.get("total", len(entries)) if isinstance(data, dict) else len(entries)

    return {"entries": entries, "total": total, "collection": collection}


@register_node("cockpit.create_entry")
async def cockpit_create_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new entry in a Cockpit collection.

    Config:
      - collection : Name of the collection (required)
      - data       : Dict of fields for the new entry (required)
    """
    collection = config.get("collection") or input_data.get("collection")
    entry_data = config.get("data") or input_data.get("data")
    if not collection:
        raise ValueError("cockpit.create_entry requires 'collection'")
    if not entry_data or not isinstance(entry_data, dict):
        raise ValueError("cockpit.create_entry requires 'data' as a dict")

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post(
            f"/collections/save/{collection}",
            json={"data": entry_data},
        )
        _raise_for_status(r)
        data = r.json()

    return {"entry": data, "collection": collection}


@register_node("cockpit.update_entry")
async def cockpit_update_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing entry in a Cockpit collection.

    Config:
      - collection : Name of the collection (required)
      - entry_id   : The _id of the entry to update (required)
      - data       : Dict of fields to update (required)
    """
    collection = config.get("collection") or input_data.get("collection")
    entry_id = config.get("entry_id") or input_data.get("entry_id")
    update_data = config.get("data") or input_data.get("data")

    if not collection:
        raise ValueError("cockpit.update_entry requires 'collection'")
    if not entry_id:
        raise ValueError("cockpit.update_entry requires 'entry_id'")
    if not update_data or not isinstance(update_data, dict):
        raise ValueError("cockpit.update_entry requires 'data' as a dict")

    # Cockpit uses the same save endpoint; include _id to indicate an update
    payload_data = dict(update_data)
    payload_data["_id"] = entry_id

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post(
            f"/collections/save/{collection}",
            json={"data": payload_data},
        )
        _raise_for_status(r)
        data = r.json()

    return {"entry": data, "collection": collection, "entry_id": entry_id}


@register_node("cockpit.delete_entry")
async def cockpit_delete_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete an entry from a Cockpit collection.

    Config:
      - collection : Name of the collection (required)
      - entry_id   : The _id of the entry to delete (required)
    """
    collection = config.get("collection") or input_data.get("collection")
    entry_id = config.get("entry_id") or input_data.get("entry_id")

    if not collection:
        raise ValueError("cockpit.delete_entry requires 'collection'")
    if not entry_id:
        raise ValueError("cockpit.delete_entry requires 'entry_id'")

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.delete(f"/collections/remove/{collection}", json={"filter": {"_id": entry_id}})
        _raise_for_status(r)
        data = r.json()

    return {"deleted": True, "collection": collection, "entry_id": entry_id, "result": data}


@register_node("cockpit.get_singleton")
async def cockpit_get_singleton(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a Cockpit singleton (single-entry content type).

    Config:
      - singleton : Name of the singleton (required)
    """
    singleton = config.get("singleton") or input_data.get("singleton")
    if not singleton:
        raise ValueError("cockpit.get_singleton requires 'singleton'")

    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.get(f"/singletons/get/{singleton}")
        _raise_for_status(r)
        data = r.json()

    return {"singleton": singleton, "data": data}
