"""Grafana integration — dashboards, annotations, alerts, datasource queries."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _grafana_client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """Return (AsyncClient, base_url) for Grafana.

    Credential fields:
      host    — Grafana hostname/IP (e.g. grafana.example.com or 10.0.0.1:3000)
      api_key — Grafana API key (Bearer token)
    """
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost:3000").rstrip("/")
    api_key = creds.get("api_key") or creds.get("token", "")
    scheme = "https" if not host.startswith("http") else ""
    base_url = f"https://{host}/api/" if not host.startswith("http") else f"{host}/api/"

    client = httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    return client, base_url


@register_node("grafana.list_dashboards")
async def grafana_list_dashboards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search/list Grafana dashboards.

    config:
      query      — search string (optional)
      tag        — filter by tag (optional)
      starred    — boolean, only return starred dashboards
      limit      — max results (default 100)
      folder_ids — list of folder IDs to restrict search
    """
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost:3000").rstrip("/")
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = f"https://{host}/api/" if not host.startswith("http") else f"{host}/api/"

    params: dict = {"type": "dash-db", "limit": int(config.get("limit", 100))}
    query = config.get("query") or input_data.get("query")
    tag = config.get("tag") or input_data.get("tag")
    starred = config.get("starred") or input_data.get("starred")
    folder_ids = config.get("folder_ids") or input_data.get("folder_ids", [])

    if query:
        params["query"] = query
    if tag:
        params["tag"] = tag
    if starred:
        params["starred"] = "true"
    if folder_ids:
        params["folderIds"] = ",".join(str(fid) for fid in folder_ids)

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get("search", params=params)
        r.raise_for_status()
        dashboards = r.json()

    log.info("grafana.list_dashboards", count=len(dashboards))
    return {"dashboards": dashboards, "count": len(dashboards)}


@register_node("grafana.get_dashboard")
async def grafana_get_dashboard(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch a single dashboard by UID or slug.

    config/input_data:
      uid  — dashboard UID (preferred)
      slug — legacy dashboard slug (fallback)
    """
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost:3000").rstrip("/")
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = f"https://{host}/api/" if not host.startswith("http") else f"{host}/api/"

    uid = config.get("uid") or input_data.get("uid")
    slug = config.get("slug") or input_data.get("slug")

    if not uid and not slug:
        raise ValueError("Either uid or slug is required for grafana.get_dashboard")

    path = f"dashboards/uid/{uid}" if uid else f"dashboards/db/{slug}"

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get(path)
        r.raise_for_status()
        data = r.json()

    dashboard = data.get("dashboard", {})
    meta = data.get("meta", {})
    log.info("grafana.get_dashboard", uid=dashboard.get("uid"), title=dashboard.get("title"))
    return {
        "dashboard": dashboard,
        "meta": meta,
        "uid": dashboard.get("uid"),
        "title": dashboard.get("title"),
        "url": meta.get("url"),
    }


@register_node("grafana.create_annotation")
async def grafana_create_annotation(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a Grafana annotation on a dashboard.

    config/input_data:
      text         — annotation text/description (required)
      time         — epoch ms (default: now)
      time_end     — epoch ms end (optional — for range annotations)
      tags         — list of strings
      dashboard_id — target dashboard numeric ID (optional)
      panel_id     — target panel numeric ID (optional)
    """
    import time as _time

    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost:3000").rstrip("/")
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = f"https://{host}/api/" if not host.startswith("http") else f"{host}/api/"

    now_ms = int(_time.time() * 1000)
    payload: dict = {
        "text": config.get("text") or input_data.get("text", "Annotation"),
        "time": config.get("time") or input_data.get("time", now_ms),
        "tags": config.get("tags") or input_data.get("tags", []),
    }
    time_end = config.get("time_end") or input_data.get("time_end")
    dashboard_id = config.get("dashboard_id") or input_data.get("dashboard_id")
    panel_id = config.get("panel_id") or input_data.get("panel_id")

    if time_end:
        payload["timeEnd"] = time_end
    if dashboard_id:
        payload["dashboardId"] = int(dashboard_id)
    if panel_id:
        payload["panelId"] = int(panel_id)

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post("annotations", json=payload)
        r.raise_for_status()
        data = r.json()

    annotation_id = data.get("id")
    log.info("grafana.create_annotation", annotation_id=annotation_id, text=payload["text"])
    return {
        "annotation_id": annotation_id,
        "message": data.get("message", "Annotation added"),
        "text": payload["text"],
    }


@register_node("grafana.query_datasource")
async def grafana_query_datasource(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Query a Grafana data source directly via the query API.

    config/input_data:
      datasource_uid — UID of the data source (required)
      expr           — PromQL/metric expression
      from_ts        — start time (default: now-1h) — can be 'now-1h' or epoch ms
      to_ts          — end time (default: now)
      step           — step interval (default: '60s')
      max_data_points — int (default 300)
    """
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost:3000").rstrip("/")
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = f"https://{host}/api/" if not host.startswith("http") else f"{host}/api/"

    ds_uid = config.get("datasource_uid") or input_data.get("datasource_uid")
    if not ds_uid:
        raise ValueError("datasource_uid is required for grafana.query_datasource")

    expr = config.get("expr") or input_data.get("expr", "")
    from_ts = config.get("from_ts") or input_data.get("from_ts", "now-1h")
    to_ts = config.get("to_ts") or input_data.get("to_ts", "now")
    step = config.get("step") or input_data.get("step", "60s")
    max_dp = int(config.get("max_data_points", 300))

    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"uid": ds_uid},
                "expr": expr,
                "maxDataPoints": max_dp,
                "intervalMs": 60000,
            }
        ],
        "from": str(from_ts),
        "to": str(to_ts),
    }

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=60,
    ) as client:
        r = await client.post("ds/query", json=payload)
        r.raise_for_status()
        data = r.json()

    results = data.get("results", {})
    frames = results.get("A", {}).get("frames", [])
    log.info("grafana.query_datasource", datasource_uid=ds_uid, frames=len(frames))
    return {
        "frames": frames,
        "frame_count": len(frames),
        "datasource_uid": ds_uid,
        "expr": expr,
    }


@register_node("grafana.list_alerts")
async def grafana_list_alerts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List Grafana alert rules (Unified Alerting).

    config:
      namespace   — alert namespace/folder to filter (optional)
      state       — alert state filter: firing | pending | inactive (optional)
      limit       — max rules to return (default 200)
    """
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost:3000").rstrip("/")
    api_key = creds.get("api_key") or creds.get("token", "")
    base_url = f"https://{host}/api/" if not host.startswith("http") else f"{host}/api/"

    params: dict = {}
    namespace = config.get("namespace") or input_data.get("namespace")
    state = config.get("state") or input_data.get("state")
    limit = int(config.get("limit", 200))

    if namespace:
        params["namespace"] = namespace
    if state:
        params["state"] = state

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get("v1/provisioning/alert-rules", params=params)
        r.raise_for_status()
        data = r.json()

    rules = data if isinstance(data, list) else data.get("rules", [])
    rules = rules[:limit]
    log.info("grafana.list_alerts", count=len(rules))
    return {
        "alert_rules": rules,
        "count": len(rules),
        "namespace": namespace,
        "state_filter": state,
    }
