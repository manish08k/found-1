"""
Algolia search integration.

Credential fields:
  - app_id:  Algolia Application ID
  - api_key: Admin or Search-Only API key

Docs: https://www.algolia.com/doc/rest-api/search/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    app_id = creds.get("app_id")
    api_key = creds.get("api_key")
    if not app_id:
        raise ValueError("Algolia credential missing 'app_id'")
    if not api_key:
        raise ValueError("Algolia credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=f"https://{app_id}.algolia.net/1",
        headers={
            "X-Algolia-Application-Id": app_id,
            "X-Algolia-API-Key": api_key,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Algolia API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


@register_node("algolia.search")
async def algolia_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /indexes/{index}/query — search an Algolia index."""
    index = config.get("index") or input_data.get("index")
    query = config.get("query") if config.get("query") is not None else input_data.get("query", "")
    if not index:
        raise ValueError("algolia.search requires 'index'")
    payload: dict = {"query": query}
    for key in ("hitsPerPage", "page", "filters", "facets", "attributesToRetrieve"):
        val = config.get(key) if config.get(key) is not None else input_data.get(key)
        if val is not None:
            payload[key] = val
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/indexes/{index}/query", json=payload)
    return _check(r)


@register_node("algolia.save_object")
async def algolia_save_object(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /indexes/{index}/{objectID} — save (upsert) an object."""
    index = config.get("index") or input_data.get("index")
    object_id = config.get("objectID") or input_data.get("objectID")
    body = config.get("object") or input_data.get("object")
    if not index:
        raise ValueError("algolia.save_object requires 'index'")
    if not body or not isinstance(body, dict):
        raise ValueError("algolia.save_object requires 'object' dict")
    if object_id:
        async with await _client(credential_id, db) as client:
            r = await client.put(f"/indexes/{index}/{object_id}", json=body)
    else:
        async with await _client(credential_id, db) as client:
            r = await client.post(f"/indexes/{index}", json=body)
    return _check(r)


@register_node("algolia.get_object")
async def algolia_get_object(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /indexes/{index}/{objectID} — retrieve a single object."""
    index = config.get("index") or input_data.get("index")
    object_id = config.get("objectID") or input_data.get("objectID")
    if not index or not object_id:
        raise ValueError("algolia.get_object requires 'index' and 'objectID'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/indexes/{index}/{object_id}")
    return _check(r)


@register_node("algolia.delete_object")
async def algolia_delete_object(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /indexes/{index}/{objectID} — delete an object."""
    index = config.get("index") or input_data.get("index")
    object_id = config.get("objectID") or input_data.get("objectID")
    if not index or not object_id:
        raise ValueError("algolia.delete_object requires 'index' and 'objectID'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/indexes/{index}/{object_id}")
    return _check(r)


@register_node("algolia.batch_write")
async def algolia_batch_write(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /indexes/{index}/batch — perform multiple write operations."""
    index = config.get("index") or input_data.get("index")
    requests = config.get("requests") or input_data.get("requests")
    if not index:
        raise ValueError("algolia.batch_write requires 'index'")
    if not requests or not isinstance(requests, list):
        raise ValueError("algolia.batch_write requires 'requests' list of operations")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/indexes/{index}/batch", json={"requests": requests})
    return _check(r)


@register_node("algolia.list_indices")
async def algolia_list_indices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /indexes — list all indices."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/indexes")
    return _check(r)


@register_node("algolia.get_index_settings")
async def algolia_get_index_settings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /indexes/{index}/settings — retrieve index settings."""
    index = config.get("index") or input_data.get("index")
    if not index:
        raise ValueError("algolia.get_index_settings requires 'index'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/indexes/{index}/settings")
    return _check(r)


@register_node("algolia.set_index_settings")
async def algolia_set_index_settings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /indexes/{index}/settings — update index settings."""
    index = config.get("index") or input_data.get("index")
    settings = config.get("settings") or input_data.get("settings")
    if not index or not settings:
        raise ValueError("algolia.set_index_settings requires 'index' and 'settings'")
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/indexes/{index}/settings", json=settings)
    return _check(r)


@register_node("algolia.add_synonym")
async def algolia_add_synonym(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /indexes/{index}/synonyms/{objectID} — add/update a synonym."""
    index = config.get("index") or input_data.get("index")
    object_id = config.get("objectID") or input_data.get("objectID")
    synonym = config.get("synonym") or input_data.get("synonym")
    if not index or not object_id or not synonym:
        raise ValueError("algolia.add_synonym requires 'index', 'objectID', and 'synonym'")
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/indexes/{index}/synonyms/{object_id}", json=synonym)
    return _check(r)


@register_node("algolia.list_synonyms")
async def algolia_list_synonyms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /indexes/{index}/synonyms/search — list synonyms."""
    index = config.get("index") or input_data.get("index")
    if not index:
        raise ValueError("algolia.list_synonyms requires 'index'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/indexes/{index}/synonyms/search", json={"query": ""})
    return _check(r)


async def test_connection(creds: dict) -> None:
    """Verify Algolia credentials by listing indices."""
    app_id = creds.get("app_id")
    api_key = creds.get("api_key")
    if not app_id or not api_key:
        raise ValueError("Algolia requires 'app_id' and 'api_key'")
    async with httpx.AsyncClient(
        base_url=f"https://{app_id}.algolia.net/1",
        headers={"X-Algolia-Application-Id": app_id, "X-Algolia-API-Key": api_key},
        timeout=15.0,
    ) as client:
        r = await client.get("/indexes")
    if not r.is_success:
        raise ValueError(f"Algolia connection failed: {r.status_code}")
