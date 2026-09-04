"""
MongoDB Atlas Data API integration.

Credential fields:
  - api_key: Atlas Data API key
  - url: Atlas Data API URL (e.g. https://data.mongodb-api.com)
  - database: default database name
  - data_source: cluster name (e.g. Cluster0)

Auth: api-key header
Base URL: {url}/app/{app_id}/endpoint/data/v1
  (simplified: POST to {url}/app/data-{region}/endpoint/data/v1/action/*)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

ATLAS_DATA_API_BASE = "https://data.mongodb-api.com/app/data-abcde/endpoint/data/v1"


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, dict]:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    url = creds.get("url", "https://data.mongodb-api.com")
    database = creds.get("database")
    data_source = creds.get("data_source", "Cluster0")
    if not api_key:
        raise ValueError("MongoDB credential is missing 'api_key'")
    if not database:
        raise ValueError("MongoDB credential is missing 'database'")
    # Build base URL - strip trailing slash
    base_url = url.rstrip("/")
    # Try to use a sensible endpoint path
    if "/endpoint/data/v1" not in base_url:
        base_url = f"{base_url}/app/data-abcde/endpoint/data/v1"
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={
            "api-key": api_key,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    defaults = {"database": database, "dataSource": data_source}
    return client, defaults


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"MongoDB API error {r.status_code}: {detail}")
    return r.json()


def _body(config: dict, input_data: dict, defaults: dict, **extra) -> dict:
    body: dict = {
        "dataSource": config.get("data_source") or input_data.get("data_source") or defaults["dataSource"],
        "database": config.get("database") or input_data.get("database") or defaults["database"],
        "collection": config.get("collection") or input_data.get("collection", ""),
    }
    body.update(extra)
    return body


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("mongodb.find")
async def mongodb_find(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/find — find documents in a collection."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    if not collection:
        raise ValueError("mongodb.find requires 'collection'")
    body = _body(config, input_data, defaults)
    body["filter"] = config.get("filter") or input_data.get("filter") or {}
    projection = config.get("projection") or input_data.get("projection")
    if projection:
        body["projection"] = projection
    sort = config.get("sort") or input_data.get("sort")
    if sort:
        body["sort"] = sort
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        body["limit"] = int(limit)
    skip = config.get("skip") or input_data.get("skip")
    if skip:
        body["skip"] = int(skip)
    async with client as c:
        r = await c.post("/action/find", json=body)
    return _check(r)


@register_node("mongodb.find_one")
async def mongodb_find_one(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/findOne — find a single document."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    if not collection:
        raise ValueError("mongodb.find_one requires 'collection'")
    body = _body(config, input_data, defaults)
    body["filter"] = config.get("filter") or input_data.get("filter") or {}
    projection = config.get("projection") or input_data.get("projection")
    if projection:
        body["projection"] = projection
    async with client as c:
        r = await c.post("/action/findOne", json=body)
    return _check(r)


@register_node("mongodb.insert_one")
async def mongodb_insert_one(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/insertOne — insert a single document."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    document = config.get("document") or input_data.get("document")
    if not collection:
        raise ValueError("mongodb.insert_one requires 'collection'")
    if not document:
        raise ValueError("mongodb.insert_one requires 'document'")
    body = _body(config, input_data, defaults)
    body["document"] = document
    async with client as c:
        r = await c.post("/action/insertOne", json=body)
    return _check(r)


@register_node("mongodb.insert_many")
async def mongodb_insert_many(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/insertMany — insert multiple documents."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    documents = config.get("documents") or input_data.get("documents")
    if not collection:
        raise ValueError("mongodb.insert_many requires 'collection'")
    if not documents:
        raise ValueError("mongodb.insert_many requires 'documents'")
    body = _body(config, input_data, defaults)
    body["documents"] = documents
    async with client as c:
        r = await c.post("/action/insertMany", json=body)
    return _check(r)


@register_node("mongodb.update_one")
async def mongodb_update_one(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/updateOne — update a single document."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    filter_ = config.get("filter") or input_data.get("filter")
    update = config.get("update") or input_data.get("update")
    if not collection:
        raise ValueError("mongodb.update_one requires 'collection'")
    if not filter_:
        raise ValueError("mongodb.update_one requires 'filter'")
    if not update:
        raise ValueError("mongodb.update_one requires 'update'")
    body = _body(config, input_data, defaults)
    body["filter"] = filter_
    body["update"] = update
    upsert = config.get("upsert") or input_data.get("upsert")
    if upsert is not None:
        body["upsert"] = bool(upsert)
    async with client as c:
        r = await c.post("/action/updateOne", json=body)
    return _check(r)


@register_node("mongodb.update_many")
async def mongodb_update_many(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/updateMany — update multiple documents."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    filter_ = config.get("filter") or input_data.get("filter")
    update = config.get("update") or input_data.get("update")
    if not collection:
        raise ValueError("mongodb.update_many requires 'collection'")
    if not filter_:
        raise ValueError("mongodb.update_many requires 'filter'")
    if not update:
        raise ValueError("mongodb.update_many requires 'update'")
    body = _body(config, input_data, defaults)
    body["filter"] = filter_
    body["update"] = update
    upsert = config.get("upsert") or input_data.get("upsert")
    if upsert is not None:
        body["upsert"] = bool(upsert)
    async with client as c:
        r = await c.post("/action/updateMany", json=body)
    return _check(r)


@register_node("mongodb.delete_one")
async def mongodb_delete_one(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/deleteOne — delete a single document."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    filter_ = config.get("filter") or input_data.get("filter")
    if not collection:
        raise ValueError("mongodb.delete_one requires 'collection'")
    if not filter_:
        raise ValueError("mongodb.delete_one requires 'filter'")
    body = _body(config, input_data, defaults)
    body["filter"] = filter_
    async with client as c:
        r = await c.post("/action/deleteOne", json=body)
    return _check(r)


@register_node("mongodb.aggregate")
async def mongodb_aggregate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/aggregate — run an aggregation pipeline."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    pipeline = config.get("pipeline") or input_data.get("pipeline")
    if not collection:
        raise ValueError("mongodb.aggregate requires 'collection'")
    if not pipeline:
        raise ValueError("mongodb.aggregate requires 'pipeline'")
    body = _body(config, input_data, defaults)
    body["pipeline"] = pipeline
    async with client as c:
        r = await c.post("/action/aggregate", json=body)
    return _check(r)


@register_node("mongodb.count")
async def mongodb_count(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /action/aggregate with $count — count documents matching a filter."""
    client, defaults = await _client(credential_id, db)
    collection = config.get("collection") or input_data.get("collection")
    if not collection:
        raise ValueError("mongodb.count requires 'collection'")
    filter_ = config.get("filter") or input_data.get("filter") or {}
    body = _body(config, input_data, defaults)
    body["pipeline"] = [{"$match": filter_}, {"$count": "count"}]
    async with client as c:
        r = await c.post("/action/aggregate", json=body)
    result = _check(r)
    docs = result.get("documents", [])
    return {"count": docs[0]["count"] if docs else 0}


async def test_connection(credential_id: str, db) -> dict:
    """Test MongoDB connection by listing documents in a dummy collection."""
    client, defaults = await _client(credential_id, db)
    body = {
        "dataSource": defaults["dataSource"],
        "database": defaults["database"],
        "collection": "_test_connection",
        "filter": {},
        "limit": 1,
    }
    async with client as c:
        r = await c.post("/action/find", json=body)
    if r.status_code in (200, 400):  # 400 may mean collection doesn't exist - still connected
        return {"ok": True, "status_code": r.status_code}
    _check(r)
    return {"ok": True}
