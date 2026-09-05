"""
TheHiveProject v5 updated API integration.

Provides case management and alert handling via the TheHive v5 API
with Bearer token authentication.

Credential fields:
  - url     : TheHive instance base URL, e.g. https://thehive.example.com
  - api_key : TheHive API key
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    api_key = creds.get("api_key")
    if not url:
        raise ValueError("TheHiveProject credential missing 'url'")
    if not api_key:
        raise ValueError("TheHiveProject credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=f"{url}/api/v1/",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"TheHiveProject API error {r.status_code}: {detail}")


@register_node("thehiveproject.list_cases")
async def thp_list_cases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List cases using TheHive v5 API."""
    limit = int(config.get("limit") or input_data.get("limit", 20))
    from_index = int(config.get("from") or input_data.get("from", 0))
    status = config.get("status") or input_data.get("status")

    query_body: dict = {
        "query": [{"_name": "listCase"}],
        "from": from_index,
        "to": from_index + limit,
    }
    if status:
        query_body["query"].append({"_name": "filter", "_field": "status", "_value": status})

    async with await _client(credential_id, db) as client:
        r = await client.post("query", json=query_body)
        _raise_for_status(r)
        data = r.json()

    cases = data if isinstance(data, list) else data.get("data", [])
    log.info("thehiveproject.list_cases", count=len(cases))
    return {"cases": cases, "total": len(cases)}


@register_node("thehiveproject.create_case")
async def thp_create_case(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new case using TheHive v5 API."""
    title = config.get("title") or input_data.get("title")
    description = config.get("description") or input_data.get("description", "")
    severity = int(config.get("severity") or input_data.get("severity", 2))
    tlp = int(config.get("tlp") or input_data.get("tlp", 2))
    pap = int(config.get("pap") or input_data.get("pap", 2))
    tags = config.get("tags") or input_data.get("tags", [])
    assignee = config.get("assignee") or input_data.get("assignee")

    if not title:
        raise ValueError("thehiveproject.create_case requires 'title'")

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    payload: dict = {
        "title": title,
        "description": description,
        "severity": severity,
        "tlp": tlp,
        "pap": pap,
        "tags": tags,
    }
    if assignee:
        payload["assignee"] = assignee

    async with await _client(credential_id, db) as client:
        r = await client.post("case", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("thehiveproject.create_case", case_id=data.get("_id"))
    return {"case": data, "case_id": data.get("_id")}


@register_node("thehiveproject.update_case")
async def thp_update_case(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing case using TheHive v5 API."""
    case_id = config.get("case_id") or input_data.get("case_id")
    if not case_id:
        raise ValueError("thehiveproject.update_case requires 'case_id'")

    updates: dict = {}
    for field in ("title", "description", "severity", "tlp", "pap", "status", "assignee"):
        val = config.get(field) or input_data.get(field)
        if val is not None:
            updates[field] = val

    tags = config.get("tags") or input_data.get("tags")
    if tags:
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        updates["tags"] = tags

    async with await _client(credential_id, db) as client:
        r = await client.patch(f"case/{case_id}", json=updates)
        _raise_for_status(r)
        data = r.json()

    log.info("thehiveproject.update_case", case_id=case_id)
    return {"case": data, "case_id": case_id}


@register_node("thehiveproject.list_alerts")
async def thp_list_alerts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List alerts using TheHive v5 API."""
    limit = int(config.get("limit") or input_data.get("limit", 20))
    from_index = int(config.get("from") or input_data.get("from", 0))
    status = config.get("status") or input_data.get("status")

    query_body: dict = {
        "query": [{"_name": "listAlert"}],
        "from": from_index,
        "to": from_index + limit,
    }
    if status:
        query_body["query"].append({"_name": "filter", "_field": "status", "_value": status})

    async with await _client(credential_id, db) as client:
        r = await client.post("query", json=query_body)
        _raise_for_status(r)
        data = r.json()

    alerts = data if isinstance(data, list) else data.get("data", [])
    log.info("thehiveproject.list_alerts", count=len(alerts))
    return {"alerts": alerts, "total": len(alerts)}
