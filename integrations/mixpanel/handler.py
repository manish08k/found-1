"""
Mixpanel integration.

Credential fields:
  - username: service account username
  - secret: service account secret
  - project_id: Mixpanel project ID

Auth: HTTP Basic (username:secret)
Base URL: https://mixpanel.com/api/2.0
Ingestion: https://api.mixpanel.com/track
"""
import base64
import json
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

MIXPANEL_API_BASE = "https://mixpanel.com/api/2.0"
MIXPANEL_INGEST_BASE = "https://api.mixpanel.com"


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, dict]:
    creds = await get_credential_data(credential_id, db)
    username = creds.get("username")
    secret = creds.get("secret")
    project_id = creds.get("project_id")
    if not username:
        raise ValueError("Mixpanel credential is missing 'username'")
    if not secret:
        raise ValueError("Mixpanel credential is missing 'secret'")
    if not project_id:
        raise ValueError("Mixpanel credential is missing 'project_id'")
    token = base64.b64encode(f"{username}:{secret}".encode()).decode()
    client = httpx.AsyncClient(
        base_url=MIXPANEL_API_BASE,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )
    return client, {"project_id": project_id, "token": token}


async def _ingest_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=MIXPANEL_INGEST_BASE,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mixpanel API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("mixpanel.track_event")
async def mixpanel_track_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /track — track a single event via ingestion API."""
    _, meta = await _client(credential_id, db)
    event = config.get("event") or input_data.get("event")
    properties = config.get("properties") or input_data.get("properties") or {}
    if not event:
        raise ValueError("mixpanel.track_event requires 'event'")
    if "token" not in properties:
        properties["token"] = meta["project_id"]
    payload = [{"event": event, "properties": properties}]
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    async with await _ingest_client(meta["token"]) as c:
        r = await c.post("/track", content=f"data={data}")
    return _check(r)


@register_node("mixpanel.import_events")
async def mixpanel_import_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /import — import historical events (requires service account auth)."""
    client, meta = await _client(credential_id, db)
    events = config.get("events") or input_data.get("events")
    if not events:
        raise ValueError("mixpanel.import_events requires 'events'")
    params = {"project_id": meta["project_id"], "strict": 1}
    async with client as c:
        r = await c.post(
            f"{MIXPANEL_INGEST_BASE}/import",
            content=json.dumps(events),
            params=params,
            headers={"Content-Type": "application/json"},
        )
    return _check(r)


@register_node("mixpanel.get_user_profile")
async def mixpanel_get_user_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /engage — get a user's profile by distinct_id."""
    client, meta = await _client(credential_id, db)
    distinct_id = config.get("distinct_id") or input_data.get("distinct_id")
    if not distinct_id:
        raise ValueError("mixpanel.get_user_profile requires 'distinct_id'")
    params = {
        "project_id": meta["project_id"],
        "where": f'properties["$distinct_id"] == "{distinct_id}"',
    }
    async with client as c:
        r = await c.get("/engage", params=params)
    return _check(r)


@register_node("mixpanel.set_user_property")
async def mixpanel_set_user_property(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /engage — set properties on a user profile."""
    _, meta = await _client(credential_id, db)
    distinct_id = config.get("distinct_id") or input_data.get("distinct_id")
    properties = config.get("properties") or input_data.get("properties")
    if not distinct_id:
        raise ValueError("mixpanel.set_user_property requires 'distinct_id'")
    if not properties:
        raise ValueError("mixpanel.set_user_property requires 'properties'")
    payload = [{
        "$token": meta["project_id"],
        "$distinct_id": distinct_id,
        "$set": properties,
    }]
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    async with await _ingest_client(meta["token"]) as c:
        r = await c.post("/engage", content=f"data={data}")
    return _check(r)


@register_node("mixpanel.increment_user_property")
async def mixpanel_increment_user_property(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /engage — increment numeric properties on a user profile."""
    _, meta = await _client(credential_id, db)
    distinct_id = config.get("distinct_id") or input_data.get("distinct_id")
    properties = config.get("properties") or input_data.get("properties")
    if not distinct_id:
        raise ValueError("mixpanel.increment_user_property requires 'distinct_id'")
    if not properties:
        raise ValueError("mixpanel.increment_user_property requires 'properties'")
    payload = [{
        "$token": meta["project_id"],
        "$distinct_id": distinct_id,
        "$add": properties,
    }]
    data = base64.b64encode(json.dumps(payload).encode()).decode()
    async with await _ingest_client(meta["token"]) as c:
        r = await c.post("/engage", content=f"data={data}")
    return _check(r)


@register_node("mixpanel.list_events")
async def mixpanel_list_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /events/names — list event names for the project."""
    client, meta = await _client(credential_id, db)
    params = {"project_id": meta["project_id"]}
    type_ = config.get("type") or input_data.get("type", "general")
    params["type"] = type_
    async with client as c:
        r = await c.get("/events/names", params=params)
    return _check(r)


@register_node("mixpanel.query_jql")
async def mixpanel_query_jql(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /jql — run a JQL query."""
    client, meta = await _client(credential_id, db)
    script = config.get("script") or input_data.get("script")
    if not script:
        raise ValueError("mixpanel.query_jql requires 'script'")
    params = config.get("params") or input_data.get("params") or {}
    body = {"script": script, "params": params}
    async with client as c:
        r = await c.post("/jql", json=body, params={"project_id": meta["project_id"]})
    return _check(r)


@register_node("mixpanel.export_events")
async def mixpanel_export_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /export — export raw events (returns NDJSON)."""
    client, meta = await _client(credential_id, db)
    from_date = config.get("from_date") or input_data.get("from_date")
    to_date = config.get("to_date") or input_data.get("to_date")
    if not from_date or not to_date:
        raise ValueError("mixpanel.export_events requires 'from_date' and 'to_date'")
    params: dict = {
        "project_id": meta["project_id"],
        "from_date": from_date,
        "to_date": to_date,
    }
    event = config.get("event") or input_data.get("event")
    if event:
        params["event"] = json.dumps([event] if isinstance(event, str) else event)
    where = config.get("where") or input_data.get("where")
    if where:
        params["where"] = where
    async with httpx.AsyncClient(
        base_url="https://data.mixpanel.com/api/2.0",
        headers={"Authorization": "Basic " + base64.b64encode(f"{meta['project_id']}:".encode()).decode()},
        timeout=60.0,
    ) as c:
        r = await c.get("/export", params=params)
    if not r.is_success:
        raise ValueError(f"Mixpanel export error {r.status_code}: {r.text}")
    lines = [json.loads(line) for line in r.text.strip().split("\n") if line.strip()]
    return {"events": lines}


@register_node("mixpanel.list_cohorts")
async def mixpanel_list_cohorts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /cohorts/list — list all cohorts in the project."""
    client, meta = await _client(credential_id, db)
    params = {"project_id": meta["project_id"]}
    async with client as c:
        r = await c.get("/cohorts/list", params=params)
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test Mixpanel connection by listing event names."""
    client, meta = await _client(credential_id, db)
    async with client as c:
        r = await c.get("/events/names", params={"project_id": meta["project_id"], "type": "general"})
    _check(r)
    return {"ok": True}
