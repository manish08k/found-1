"""Couchbase integration — document get/upsert/delete/insert and N1QL queries."""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _get_cluster(connection_string: str, username: str, password: str):
    """Connect to a Couchbase cluster and return (cluster, bucket_fn)."""
    try:
        from couchbase.cluster import Cluster
        from couchbase.options import ClusterOptions
        from couchbase.auth import PasswordAuthenticator
    except ImportError as exc:
        raise ImportError(
            "couchbase SDK is not installed. Install it with: pip install couchbase"
        ) from exc

    auth = PasswordAuthenticator(username, password)
    cluster = Cluster(connection_string, ClusterOptions(auth))
    cluster.wait_until_ready(timeout=10)
    return cluster


@register_node("couchbase.get_document")
async def couchbase_get_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a document from a Couchbase bucket by key.

    config:
      connection_string — Couchbase connection string e.g. couchbase://localhost (required)
      username          — Couchbase username (required)
      password          — Couchbase password (required)
      bucket_name       — bucket name (required)
      key               — document key to retrieve (required)
      scope             — scope name (optional, default _default)
      collection        — collection name (optional, default _default)
    """
    merged = {**config, **input_data}
    connection_string = merged.get("connection_string", "")
    username = merged.get("username", "")
    password = merged.get("password", "")
    bucket_name = merged.get("bucket_name", "")
    key = merged.get("key")
    if not all([connection_string, username, password, bucket_name, key]):
        raise ValueError("connection_string, username, password, bucket_name, and key are required")

    cluster = _get_cluster(connection_string, username, password)
    bucket = cluster.bucket(bucket_name)
    scope_name = merged.get("scope", "_default")
    collection_name = merged.get("collection", "_default")
    collection = bucket.scope(scope_name).collection(collection_name)

    result = collection.get(key)
    document = result.content_as[dict]

    log.info("couchbase.get_document", bucket=bucket_name, key=key)
    return {"document": document, "key": key, "cas": str(result.cas)}


@register_node("couchbase.upsert_document")
async def couchbase_upsert_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upsert (insert or replace) a document in a Couchbase bucket.

    config:
      connection_string — Couchbase connection string (required)
      username          — Couchbase username (required)
      password          — Couchbase password (required)
      bucket_name       — bucket name (required)
      key               — document key (required)
      document          — document content as dict (required)
      scope             — scope name (optional, default _default)
      collection        — collection name (optional, default _default)
    """
    merged = {**config, **input_data}
    connection_string = merged.get("connection_string", "")
    username = merged.get("username", "")
    password = merged.get("password", "")
    bucket_name = merged.get("bucket_name", "")
    key = merged.get("key")
    document = merged.get("document", {})
    if not all([connection_string, username, password, bucket_name, key]):
        raise ValueError("connection_string, username, password, bucket_name, and key are required")

    cluster = _get_cluster(connection_string, username, password)
    bucket = cluster.bucket(bucket_name)
    scope_name = merged.get("scope", "_default")
    collection_name = merged.get("collection", "_default")
    collection = bucket.scope(scope_name).collection(collection_name)

    result = collection.upsert(key, document)

    log.info("couchbase.upsert_document", bucket=bucket_name, key=key)
    return {"success": True, "key": key, "cas": str(result.cas)}


@register_node("couchbase.insert_document")
async def couchbase_insert_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Insert a new document in a Couchbase bucket (fails if key exists).

    config:
      connection_string — Couchbase connection string (required)
      username          — Couchbase username (required)
      password          — Couchbase password (required)
      bucket_name       — bucket name (required)
      key               — document key (required)
      document          — document content as dict (required)
      scope             — scope name (optional, default _default)
      collection        — collection name (optional, default _default)
    """
    merged = {**config, **input_data}
    connection_string = merged.get("connection_string", "")
    username = merged.get("username", "")
    password = merged.get("password", "")
    bucket_name = merged.get("bucket_name", "")
    key = merged.get("key")
    document = merged.get("document", {})
    if not all([connection_string, username, password, bucket_name, key]):
        raise ValueError("connection_string, username, password, bucket_name, and key are required")

    cluster = _get_cluster(connection_string, username, password)
    bucket = cluster.bucket(bucket_name)
    scope_name = merged.get("scope", "_default")
    collection_name = merged.get("collection", "_default")
    collection = bucket.scope(scope_name).collection(collection_name)

    result = collection.insert(key, document)

    log.info("couchbase.insert_document", bucket=bucket_name, key=key)
    return {"success": True, "key": key, "cas": str(result.cas)}


@register_node("couchbase.delete_document")
async def couchbase_delete_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a document from a Couchbase bucket by key.

    config:
      connection_string — Couchbase connection string (required)
      username          — Couchbase username (required)
      password          — Couchbase password (required)
      bucket_name       — bucket name (required)
      key               — document key to delete (required)
      scope             — scope name (optional, default _default)
      collection        — collection name (optional, default _default)
    """
    merged = {**config, **input_data}
    connection_string = merged.get("connection_string", "")
    username = merged.get("username", "")
    password = merged.get("password", "")
    bucket_name = merged.get("bucket_name", "")
    key = merged.get("key")
    if not all([connection_string, username, password, bucket_name, key]):
        raise ValueError("connection_string, username, password, bucket_name, and key are required")

    cluster = _get_cluster(connection_string, username, password)
    bucket = cluster.bucket(bucket_name)
    scope_name = merged.get("scope", "_default")
    collection_name = merged.get("collection", "_default")
    collection = bucket.scope(scope_name).collection(collection_name)

    collection.remove(key)

    log.info("couchbase.delete_document", bucket=bucket_name, key=key)
    return {"success": True, "key": key}


@register_node("couchbase.query")
async def couchbase_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a N1QL query against Couchbase.

    config:
      connection_string — Couchbase connection string (required)
      username          — Couchbase username (required)
      password          — Couchbase password (required)
      bucket_name       — bucket name (optional, for context)
      query             — N1QL query string (required)
      parameters        — list of positional parameters (optional)
    """
    merged = {**config, **input_data}
    connection_string = merged.get("connection_string", "")
    username = merged.get("username", "")
    password = merged.get("password", "")
    query = merged.get("query")
    if not all([connection_string, username, password, query]):
        raise ValueError("connection_string, username, password, and query are required")

    try:
        from couchbase.options import QueryOptions
    except ImportError:
        QueryOptions = None  # type: ignore

    cluster = _get_cluster(connection_string, username, password)
    parameters = merged.get("parameters", [])

    if parameters and QueryOptions:
        result = cluster.query(query, QueryOptions(positional_parameters=parameters))
    else:
        result = cluster.query(query)

    rows = [row for row in result]

    log.info("couchbase.query", row_count=len(rows))
    return {"rows": rows, "count": len(rows)}
