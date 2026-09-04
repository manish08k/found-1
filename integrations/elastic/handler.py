"""
Elasticsearch search and analytics integration.

Credential fields:
  - url: Elasticsearch cluster URL (e.g. https://my-cluster.es.io:9243)
  - api_key: Elasticsearch API key (preferred)
  - username: Basic auth username (if api_key not provided)
  - password: Basic auth password (if api_key not provided)

Auth: api_key header (ApiKey base64) OR Basic auth
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    if not url:
        raise ValueError("Elasticsearch credential is missing 'url'")
    api_key = creds.get("api_key")
    username = creds.get("username")
    password = creds.get("password")
    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    elif username and password:
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    else:
        raise ValueError("Elasticsearch credential requires 'api_key' OR 'username'+'password'")
    return httpx.AsyncClient(base_url=url, headers=headers, timeout=30.0)


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Elasticsearch API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------

@register_node("elastic.index_document")
async def elastic_index_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /{index}/_doc/{id} or POST /{index}/_doc — index a document."""
    index = config.get("index") or input_data.get("index")
    document = config.get("document") or input_data.get("document")
    if not index:
        raise ValueError("elastic.index_document requires 'index'")
    if document is None:
        raise ValueError("elastic.index_document requires 'document'")
    doc_id = config.get("id") or input_data.get("id")
    async with await _client(credential_id, db) as client:
        if doc_id:
            r = await client.put(f"/{index}/_doc/{doc_id}", json=document)
        else:
            r = await client.post(f"/{index}/_doc", json=document)
    return _check(r)


@register_node("elastic.get_document")
async def elastic_get_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /{index}/_doc/{id} — retrieve a document by ID."""
    index = config.get("index") or input_data.get("index")
    doc_id = config.get("id") or input_data.get("id")
    if not index or not doc_id:
        raise ValueError("elastic.get_document requires 'index' and 'id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{index}/_doc/{doc_id}")
    return _check(r)


@register_node("elastic.update_document")
async def elastic_update_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /{index}/_update/{id} — update a document by ID."""
    index = config.get("index") or input_data.get("index")
    doc_id = config.get("id") or input_data.get("id")
    update_body = config.get("update") or input_data.get("update")
    if not index or not doc_id:
        raise ValueError("elastic.update_document requires 'index' and 'id'")
    if update_body is None:
        raise ValueError("elastic.update_document requires 'update' (e.g. {\"doc\": {...}})")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/{index}/_update/{doc_id}", json=update_body)
    return _check(r)


@register_node("elastic.delete_document")
async def elastic_delete_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /{index}/_doc/{id} — delete a document by ID."""
    index = config.get("index") or input_data.get("index")
    doc_id = config.get("id") or input_data.get("id")
    if not index or not doc_id:
        raise ValueError("elastic.delete_document requires 'index' and 'id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/{index}/_doc/{doc_id}")
    return _check(r)


@register_node("elastic.search")
async def elastic_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /{index}/_search — execute a search query."""
    index = config.get("index") or input_data.get("index") or "_all"
    query = config.get("query") or input_data.get("query") or {"match_all": {}}
    body: dict = {"query": query}
    size = config.get("size") or input_data.get("size")
    if size:
        body["size"] = int(size)
    from_val = config.get("from") or input_data.get("from")
    if from_val:
        body["from"] = int(from_val)
    sort = config.get("sort") or input_data.get("sort")
    if sort:
        body["sort"] = sort
    source = config.get("_source") or input_data.get("_source")
    if source is not None:
        body["_source"] = source
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/{index}/_search", json=body)
    return _check(r)


@register_node("elastic.bulk_index")
async def elastic_bulk_index(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /_bulk — bulk index documents using NDJSON format."""
    index = config.get("index") or input_data.get("index")
    documents = config.get("documents") or input_data.get("documents")
    if not documents:
        raise ValueError("elastic.bulk_index requires 'documents' (list of dicts)")
    lines = []
    for doc in documents:
        meta: dict = {"index": {}}
        if index:
            meta["index"]["_index"] = index
        doc_id = doc.pop("_id", None)
        if doc_id:
            meta["index"]["_id"] = doc_id
        lines.append(meta)
        lines.append(doc)
    import json
    ndjson = "\n".join(json.dumps(line) for line in lines) + "\n"
    creds_obj = await _client(credential_id, db)
    async with creds_obj as client:
        r = await client.post(
            "/_bulk",
            content=ndjson,
            headers={"Content-Type": "application/x-ndjson"},
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------

@register_node("elastic.create_index")
async def elastic_create_index(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /{index} — create a new index."""
    index = config.get("index") or input_data.get("index")
    if not index:
        raise ValueError("elastic.create_index requires 'index'")
    body: dict = {}
    mappings = config.get("mappings") or input_data.get("mappings")
    if mappings:
        body["mappings"] = mappings
    settings = config.get("settings") or input_data.get("settings")
    if settings:
        body["settings"] = settings
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/{index}", json=body)
    return _check(r)


@register_node("elastic.delete_index")
async def elastic_delete_index(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /{index} — delete an index."""
    index = config.get("index") or input_data.get("index")
    if not index:
        raise ValueError("elastic.delete_index requires 'index'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/{index}")
    return _check(r)


@register_node("elastic.list_indices")
async def elastic_list_indices(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /_cat/indices — list all indices."""
    params = {"format": "json"}
    pattern = config.get("pattern") or input_data.get("pattern") or "*"
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/_cat/indices/{pattern}", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Cluster
# ---------------------------------------------------------------------------

@register_node("elastic.get_cluster_health")
async def elastic_get_cluster_health(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /_cluster/health — get cluster health status."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/_cluster/health")
    return _check(r)


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

@register_node("elastic.create_snapshot")
async def elastic_create_snapshot(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /_snapshot/{repository}/{snapshot} — create a snapshot."""
    repository = config.get("repository") or input_data.get("repository")
    snapshot = config.get("snapshot") or input_data.get("snapshot")
    if not repository or not snapshot:
        raise ValueError("elastic.create_snapshot requires 'repository' and 'snapshot'")
    body: dict = {}
    indices = config.get("indices") or input_data.get("indices")
    if indices:
        body["indices"] = indices
    include_global_state = config.get("include_global_state")
    if include_global_state is None:
        include_global_state = input_data.get("include_global_state")
    if include_global_state is not None:
        body["include_global_state"] = bool(include_global_state)
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/_snapshot/{repository}/{snapshot}", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test Elasticsearch connection by checking cluster health."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/_cluster/health")
    _check(r)
    data = r.json()
    return {"ok": True, "cluster_name": data.get("cluster_name", "unknown"), "status": data.get("status")}
