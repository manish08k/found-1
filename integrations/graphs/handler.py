"""
Graph database nodes — Neo4j via HTTP API.

Nodes:
  graph.neo4j.query         — run a Cypher query, return rows
  graph.neo4j.create_node   — create a node with labels and properties
  graph.neo4j.merge_node    — MERGE a node (upsert by matching properties)
  graph.neo4j.delete_node   — delete a node by ID or match
  graph.neo4j.create_rel    — create a relationship between two nodes
  graph.neo4j.schema        — return the graph schema (node labels + properties)
"""
import json
import re

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _neo4j_http(config: dict) -> tuple[str, tuple[str, str]]:
    """Return (http_url, (user, password)) from config or settings."""
    raw_url = config.get("url") or getattr(settings, "NEO4J_URL", "bolt://localhost:7687")
    # Convert bolt:// → http://, keeping host; bolt default 7687 → HTTP 7474
    http_url = raw_url
    if http_url.startswith("bolt://") or http_url.startswith("neo4j://"):
        http_url = re.sub(r"^(bolt|neo4j)://", "http://", http_url)
        http_url = re.sub(r":7687(/|$)", ":7474\\1", http_url)
    elif not http_url.startswith("http"):
        http_url = f"http://{http_url}"
    http_url = http_url.rstrip("/")

    user = config.get("username") or getattr(settings, "NEO4J_USER", "neo4j")
    password = config.get("password") or getattr(settings, "NEO4J_PASSWORD", "")
    db = config.get("database", "neo4j")
    return f"{http_url}/db/{db}/tx/commit", (user, password)


async def _run_cypher(url: str, auth: tuple[str, str], query: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher statement and return rows as list of dicts."""
    body = {"statements": [{"statement": query, "parameters": params or {}}]}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, auth=auth, json=body,
                         headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()

    errors = data.get("errors", [])
    if errors:
        raise RuntimeError(f"Neo4j error: {errors[0].get('message', str(errors))}")

    results = data.get("results", [])
    if not results or not results[0].get("data"):
        return []

    cols = results[0].get("columns", [])
    rows = []
    for row_data in results[0]["data"]:
        row_vals = row_data.get("row", [])
        rows.append(dict(zip(cols, row_vals)))
    return rows


# ─── graph.neo4j.query ───────────────────────────────────────────────────────

@register_node("graph.neo4j.query")
async def graph_neo4j_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Run an arbitrary Cypher query.
    config: url, username, password, database
    input_data: query (str), params (dict)
    """
    url, auth = _neo4j_http(config)
    query = input_data.get("query") or config.get("query", "RETURN 1 AS n")
    params = input_data.get("params") or config.get("params") or {}

    rows = await _run_cypher(url, auth, query, params)
    return {"rows": rows, "count": len(rows), "query": query}


# ─── graph.neo4j.create_node ─────────────────────────────────────────────────

@register_node("graph.neo4j.create_node")
async def graph_neo4j_create_node(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Create a node with the specified labels and properties.
    config: labels (list or str), properties (dict)
    input_data: properties (merged with config.properties)
    """
    url, auth = _neo4j_http(config)
    labels = config.get("labels", ["Node"])
    if isinstance(labels, str):
        labels = [labels]
    label_str = ":".join(labels)

    props = {**config.get("properties", {}), **{k: v for k, v in input_data.items() if k not in ("query", "params")}}

    cypher = f"CREATE (n:{label_str} $props) RETURN id(n) AS node_id, n"
    rows = await _run_cypher(url, auth, cypher, {"props": props})

    node_id = rows[0].get("node_id") if rows else None
    return {"node_id": node_id, "labels": labels, "properties": props, "created": True}


# ─── graph.neo4j.merge_node ──────────────────────────────────────────────────

@register_node("graph.neo4j.merge_node")
async def graph_neo4j_merge_node(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    MERGE a node by match_properties, then SET update_properties.
    config: labels, match_properties (dict — keys used in MERGE), update_properties (dict)
    """
    url, auth = _neo4j_http(config)
    labels = config.get("labels", ["Node"])
    if isinstance(labels, str):
        labels = [labels]
    label_str = ":".join(labels)

    match_props = config.get("match_properties") or {}
    update_props = {**config.get("update_properties", {}), **{k: v for k, v in input_data.items() if k not in ("query", "params")}}

    cypher = (
        f"MERGE (n:{label_str} $match_props) "
        f"ON CREATE SET n += $update_props "
        f"ON MATCH SET n += $update_props "
        f"RETURN id(n) AS node_id, n"
    )
    rows = await _run_cypher(url, auth, cypher, {"match_props": match_props, "update_props": update_props})
    node_id = rows[0].get("node_id") if rows else None
    return {"node_id": node_id, "labels": labels, "merged": True}


# ─── graph.neo4j.delete_node ─────────────────────────────────────────────────

@register_node("graph.neo4j.delete_node")
async def graph_neo4j_delete_node(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Delete a node by internal Neo4j ID or by matching properties.
    config: by_id (int) OR match_properties (dict) + labels, detach (bool)
    """
    url, auth = _neo4j_http(config)
    by_id = config.get("node_id") or input_data.get("node_id")
    match_props = config.get("match_properties") or input_data.get("match_properties") or {}
    labels = config.get("labels", [])
    label_str = (":".join(labels) if labels else "")
    detach = "DETACH " if config.get("detach", True) else ""

    if by_id is not None:
        cypher = f"MATCH (n) WHERE id(n) = $nid {detach}DELETE n RETURN count(n) AS deleted"
        rows = await _run_cypher(url, auth, cypher, {"nid": int(by_id)})
    else:
        label_clause = f":{label_str}" if label_str else ""
        cypher = f"MATCH (n{label_clause} $props) {detach}DELETE n RETURN count(n) AS deleted"
        rows = await _run_cypher(url, auth, cypher, {"props": match_props})

    deleted = rows[0].get("deleted", 0) if rows else 0
    return {"deleted": deleted}


# ─── graph.neo4j.create_rel ──────────────────────────────────────────────────

@register_node("graph.neo4j.create_rel")
async def graph_neo4j_create_rel(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Create a relationship between two nodes identified by node IDs or match properties.
    config:
      from_id / from_props + from_labels  — source node
      to_id / to_props + to_labels        — target node
      rel_type (str)                      — relationship type
      properties (dict)                   — relationship properties
    """
    url, auth = _neo4j_http(config)
    rel_type = config.get("rel_type", "RELATED_TO").upper()
    rel_props = config.get("properties", {})

    from_id = config.get("from_id") or input_data.get("from_id")
    to_id = config.get("to_id") or input_data.get("to_id")

    if from_id and to_id:
        cypher = (
            f"MATCH (a), (b) WHERE id(a)=$from_id AND id(b)=$to_id "
            f"CREATE (a)-[r:{rel_type} $props]->(b) "
            f"RETURN id(r) AS rel_id, type(r) AS rel_type"
        )
        params = {"from_id": int(from_id), "to_id": int(to_id), "props": rel_props}
    else:
        from_labels = config.get("from_labels", ["Node"])
        to_labels = config.get("to_labels", ["Node"])
        from_props = config.get("from_props", {})
        to_props = config.get("to_props", {})
        fl = ":".join(from_labels) if from_labels else "Node"
        tl = ":".join(to_labels) if to_labels else "Node"
        cypher = (
            f"MATCH (a:{fl} $from_props), (b:{tl} $to_props) "
            f"CREATE (a)-[r:{rel_type} $props]->(b) "
            f"RETURN id(r) AS rel_id, type(r) AS rel_type"
        )
        params = {"from_props": from_props, "to_props": to_props, "props": rel_props}

    rows = await _run_cypher(url, auth, cypher, params)
    rel_id = rows[0].get("rel_id") if rows else None
    return {"rel_id": rel_id, "rel_type": rel_type, "properties": rel_props, "created": True}


# ─── graph.neo4j.schema ──────────────────────────────────────────────────────

@register_node("graph.neo4j.schema")
async def graph_neo4j_schema(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Return the graph schema: node labels, relationship types, and property keys.
    """
    url, auth = _neo4j_http(config)

    labels_rows = await _run_cypher(url, auth, "CALL db.labels() YIELD label RETURN label")
    rel_rows = await _run_cypher(url, auth, "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
    prop_rows = await _run_cypher(url, auth, "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey")

    labels = [r.get("label") for r in labels_rows]
    rel_types = [r.get("relationshipType") for r in rel_rows]
    prop_keys = [r.get("propertyKey") for r in prop_rows]

    # Build a readable schema description
    schema_str = (
        f"Node labels: {', '.join(labels)}\n"
        f"Relationship types: {', '.join(rel_types)}\n"
        f"Property keys: {', '.join(prop_keys)}"
    )
    return {"labels": labels, "relationship_types": rel_types, "property_keys": prop_keys, "schema": schema_str}
