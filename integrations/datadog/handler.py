"""
Datadog monitoring and observability integration.

Credential fields:
  - api_key: Datadog API key (DD-API-KEY header)
  - app_key: Datadog Application key (DD-APPLICATION-KEY header)

Auth: DD-API-KEY + DD-APPLICATION-KEY headers
Base URL v1: https://api.datadoghq.com/api/v1
Base URL v2: https://api.datadoghq.com/api/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

DATADOG_BASE_V1 = "https://api.datadoghq.com/api/v1"
DATADOG_BASE_V2 = "https://api.datadoghq.com/api/v2"


async def _get_headers(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    app_key = creds.get("app_key")
    if not api_key:
        raise ValueError("Datadog credential is missing 'api_key'")
    if not app_key:
        raise ValueError("Datadog credential is missing 'app_key'")
    return {
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
        "Content-Type": "application/json",
    }


async def _client_v1(credential_id: str, db) -> httpx.AsyncClient:
    headers = await _get_headers(credential_id, db)
    return httpx.AsyncClient(base_url=DATADOG_BASE_V1, headers=headers, timeout=30.0)


async def _client_v2(credential_id: str, db) -> httpx.AsyncClient:
    headers = await _get_headers(credential_id, db)
    return httpx.AsyncClient(base_url=DATADOG_BASE_V2, headers=headers, timeout=30.0)


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Datadog API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


# ---------------------------------------------------------------------------
# Metrics (v1)
# ---------------------------------------------------------------------------

@register_node("datadog.create_metric")
async def datadog_create_metric(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /series — submit metric data points."""
    series = config.get("series") or input_data.get("series")
    if not series:
        raise ValueError("datadog.create_metric requires 'series' (list of metric series objects)")
    body = {"series": series if isinstance(series, list) else [series]}
    async with await _client_v1(credential_id, db) as client:
        r = await client.post("/series", json=body)
    return _check(r)


@register_node("datadog.list_metrics")
async def datadog_list_metrics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /metrics — list active metrics from a given time."""
    from_ts = config.get("from") or input_data.get("from")
    if not from_ts:
        raise ValueError("datadog.list_metrics requires 'from' (Unix timestamp)")
    params = {"from": int(from_ts)}
    host = config.get("host") or input_data.get("host")
    if host:
        params["host"] = host
    async with await _client_v1(credential_id, db) as client:
        r = await client.get("/metrics", params=params)
    return _check(r)


@register_node("datadog.get_metric_metadata")
async def datadog_get_metric_metadata(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /metrics/{metric_name} — get metadata for a metric."""
    metric_name = config.get("metric_name") or input_data.get("metric_name")
    if not metric_name:
        raise ValueError("datadog.get_metric_metadata requires 'metric_name'")
    async with await _client_v1(credential_id, db) as client:
        r = await client.get(f"/metrics/{metric_name}")
    return _check(r)


# ---------------------------------------------------------------------------
# Events (v1)
# ---------------------------------------------------------------------------

@register_node("datadog.create_event")
async def datadog_create_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /events — create an event."""
    title = config.get("title") or input_data.get("title")
    text = config.get("text") or input_data.get("text")
    if not title or not text:
        raise ValueError("datadog.create_event requires 'title' and 'text'")
    body: dict = {"title": title, "text": text}
    for field in ("alert_type", "priority", "tags", "host", "date_happened"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client_v1(credential_id, db) as client:
        r = await client.post("/events", json=body)
    return _check(r)


@register_node("datadog.list_events")
async def datadog_list_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /events — query events over a time range."""
    start = config.get("start") or input_data.get("start")
    end = config.get("end") or input_data.get("end")
    if not start or not end:
        raise ValueError("datadog.list_events requires 'start' and 'end' (Unix timestamps)")
    params: dict = {"start": int(start), "end": int(end)}
    priority = config.get("priority") or input_data.get("priority")
    if priority:
        params["priority"] = priority
    tags = config.get("tags") or input_data.get("tags")
    if tags:
        params["tags"] = tags
    async with await _client_v1(credential_id, db) as client:
        r = await client.get("/events", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Monitors (v1)
# ---------------------------------------------------------------------------

@register_node("datadog.list_monitors")
async def datadog_list_monitors(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /monitor — list all monitors."""
    params = {}
    tags = config.get("tags") or input_data.get("tags")
    if tags:
        params["monitor_tags"] = tags
    monitor_type = config.get("type") or input_data.get("type")
    if monitor_type:
        params["type"] = monitor_type
    async with await _client_v1(credential_id, db) as client:
        r = await client.get("/monitor", params=params)
    return _check(r)


@register_node("datadog.create_monitor")
async def datadog_create_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /monitor — create a new monitor."""
    monitor_type = config.get("type") or input_data.get("type")
    query = config.get("query") or input_data.get("query")
    name = config.get("name") or input_data.get("name")
    if not monitor_type or not query or not name:
        raise ValueError("datadog.create_monitor requires 'type', 'query', and 'name'")
    body: dict = {"type": monitor_type, "query": query, "name": name}
    for field in ("message", "tags", "options", "priority"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client_v1(credential_id, db) as client:
        r = await client.post("/monitor", json=body)
    return _check(r)


@register_node("datadog.update_monitor")
async def datadog_update_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /monitor/{monitor_id} — update an existing monitor."""
    monitor_id = config.get("monitor_id") or input_data.get("monitor_id")
    if not monitor_id:
        raise ValueError("datadog.update_monitor requires 'monitor_id'")
    body: dict = {}
    for field in ("name", "type", "query", "message", "tags", "options", "priority"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client_v1(credential_id, db) as client:
        r = await client.put(f"/monitor/{monitor_id}", json=body)
    return _check(r)


@register_node("datadog.mute_monitor")
async def datadog_mute_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /monitor/{monitor_id}/mute — mute a monitor."""
    monitor_id = config.get("monitor_id") or input_data.get("monitor_id")
    if not monitor_id:
        raise ValueError("datadog.mute_monitor requires 'monitor_id'")
    body: dict = {}
    end = config.get("end") or input_data.get("end")
    if end:
        body["end"] = end
    scope = config.get("scope") or input_data.get("scope")
    if scope:
        body["scope"] = scope
    async with await _client_v1(credential_id, db) as client:
        r = await client.post(f"/monitor/{monitor_id}/mute", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Dashboards (v1)
# ---------------------------------------------------------------------------

@register_node("datadog.list_dashboards")
async def datadog_list_dashboards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /dashboard — list all dashboards."""
    async with await _client_v1(credential_id, db) as client:
        r = await client.get("/dashboard")
    return _check(r)


# ---------------------------------------------------------------------------
# Service Checks (v1)
# ---------------------------------------------------------------------------

@register_node("datadog.get_service_checks")
async def datadog_get_service_checks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /check_run — get service check summaries."""
    async with await _client_v1(credential_id, db) as client:
        r = await client.get("/check_run")
    return _check(r)


# ---------------------------------------------------------------------------
# Logs (v2)
# ---------------------------------------------------------------------------

@register_node("datadog.list_logs")
async def datadog_list_logs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /logs/events/search — search logs (v2)."""
    body: dict = {}
    query_filter = config.get("filter") or input_data.get("filter")
    if query_filter:
        body["filter"] = query_filter
    else:
        body["filter"] = {}
    from_ts = config.get("from") or input_data.get("from")
    if from_ts:
        body["filter"]["from"] = from_ts
    to_ts = config.get("to") or input_data.get("to")
    if to_ts:
        body["filter"]["to"] = to_ts
    query = config.get("query") or input_data.get("query")
    if query:
        body["filter"]["query"] = query
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        body["page"] = {"limit": int(limit)}
    async with await _client_v2(credential_id, db) as client:
        r = await client.post("/logs/events/search", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test Datadog connection by validating the API key."""
    async with await _client_v1(credential_id, db) as client:
        r = await client.get("/validate")
    _check(r)
    return {"ok": True, "message": "Datadog connection successful"}
