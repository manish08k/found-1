"""
TheHive security incident response integration.

Provides case management, alert creation, and observable listing via
the TheHive API with Bearer token authentication.

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
        raise ValueError("TheHive credential missing 'url'")
    if not api_key:
        raise ValueError("TheHive credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=f"{url}/api/",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"TheHive API error {r.status_code}: {detail}")


@register_node("thehive.list_cases")
async def thehive_list_cases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List cases from TheHive."""
    limit = int(config.get("limit") or input_data.get("limit", 20))
    offset = int(config.get("offset") or input_data.get("offset", 0))
    status = config.get("status") or input_data.get("status")

    params: dict = {"range": f"{offset}-{offset + limit}"}
    if status:
        params["status"] = status

    async with await _client(credential_id, db) as client:
        r = await client.get("case", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("thehive.list_cases", count=len(data) if isinstance(data, list) else 0)
    return {"cases": data if isinstance(data, list) else [], "total": len(data) if isinstance(data, list) else 0}


@register_node("thehive.create_case")
async def thehive_create_case(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new case in TheHive."""
    title = config.get("title") or input_data.get("title")
    description = config.get("description") or input_data.get("description", "")
    severity = int(config.get("severity") or input_data.get("severity", 2))
    tlp = int(config.get("tlp") or input_data.get("tlp", 2))
    tags = config.get("tags") or input_data.get("tags", [])
    flag = bool(config.get("flag") or input_data.get("flag", False))

    if not title:
        raise ValueError("thehive.create_case requires 'title'")

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    payload = {
        "title": title,
        "description": description,
        "severity": severity,
        "tlp": tlp,
        "tags": tags,
        "flag": flag,
    }

    async with await _client(credential_id, db) as client:
        r = await client.post("case", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("thehive.create_case", case_id=data.get("id"))
    return {"case": data, "case_id": data.get("id")}


@register_node("thehive.create_alert")
async def thehive_create_alert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create an alert in TheHive."""
    title = config.get("title") or input_data.get("title")
    description = config.get("description") or input_data.get("description", "")
    alert_type = config.get("type") or input_data.get("type", "external")
    source = config.get("source") or input_data.get("source", "automation")
    source_ref = config.get("source_ref") or input_data.get("source_ref", "")
    severity = int(config.get("severity") or input_data.get("severity", 2))
    tlp = int(config.get("tlp") or input_data.get("tlp", 2))
    tags = config.get("tags") or input_data.get("tags", [])

    if not title:
        raise ValueError("thehive.create_alert requires 'title'")

    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    payload = {
        "title": title,
        "description": description,
        "type": alert_type,
        "source": source,
        "sourceRef": source_ref or f"alert-{title[:20]}",
        "severity": severity,
        "tlp": tlp,
        "tags": tags,
        "artifacts": [],
    }

    async with await _client(credential_id, db) as client:
        r = await client.post("alert", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("thehive.create_alert", alert_id=data.get("id"))
    return {"alert": data, "alert_id": data.get("id")}


@register_node("thehive.list_observables")
async def thehive_list_observables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List observables for a given case."""
    case_id = config.get("case_id") or input_data.get("case_id")
    if not case_id:
        raise ValueError("thehive.list_observables requires 'case_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"case/{case_id}/artifact")
        _raise_for_status(r)
        data = r.json()

    log.info("thehive.list_observables", case_id=case_id, count=len(data) if isinstance(data, list) else 0)
    return {"observables": data if isinstance(data, list) else [], "case_id": case_id}
