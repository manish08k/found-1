"""
MISP (Malware Information Sharing Platform) threat intelligence integration.

Provides event and attribute management via the MISP REST API.

Credential fields:
  - url     : Base URL of the MISP instance, e.g. https://misp.example.com
  - api_key : MISP automation key (found in Event Actions > Automation)

Auth: Authorization header with the raw API key.
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
        raise ValueError("MISP credential missing 'url'")
    if not api_key:
        raise ValueError("MISP credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=f"{url}/",
        headers={
            "Authorization": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"MISP API error {r.status_code}: {detail}")


@register_node("misp.create_event")
async def misp_create_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new MISP event."""
    info = config.get("info") or input_data.get("info")
    if not info:
        raise ValueError("misp.create_event requires 'info' (event description)")

    distribution = int(config.get("distribution") or input_data.get("distribution", 0))
    threat_level_id = int(config.get("threat_level_id") or input_data.get("threat_level_id", 2))
    analysis = int(config.get("analysis") or input_data.get("analysis", 0))
    org_id = config.get("org_id") or input_data.get("org_id", "1")

    payload = {
        "Event": {
            "info": info,
            "distribution": distribution,
            "threat_level_id": threat_level_id,
            "analysis": analysis,
            "org_id": str(org_id),
        }
    }

    log.info("misp.create_event", info=info)
    async with await _client(credential_id, db) as client:
        r = await client.post("events", json=payload)
        _raise_for_status(r)
        data = r.json()

    event = data.get("Event", data)
    return {"event": event, "event_id": event.get("id")}


@register_node("misp.list_events")
async def misp_list_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List MISP events with optional filters."""
    limit = int(config.get("limit") or input_data.get("limit", 25))
    page = int(config.get("page") or input_data.get("page", 1))
    tags = config.get("tags") or input_data.get("tags")

    params: dict = {"limit": limit, "page": page}
    if tags:
        params["tags"] = tags

    log.info("misp.list_events", limit=limit, page=page)
    async with await _client(credential_id, db) as client:
        r = await client.get("events/index", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"events": data if isinstance(data, list) else data.get("response", []), "count": len(data) if isinstance(data, list) else len(data.get("response", []))}


@register_node("misp.add_attribute")
async def misp_add_attribute(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add an attribute to an existing MISP event."""
    event_id = config.get("event_id") or input_data.get("event_id")
    attribute_type = config.get("type") or input_data.get("type")
    value = config.get("value") or input_data.get("value")

    if not event_id:
        raise ValueError("misp.add_attribute requires 'event_id'")
    if not attribute_type:
        raise ValueError("misp.add_attribute requires 'type' (e.g. ip-src, domain, md5)")
    if not value:
        raise ValueError("misp.add_attribute requires 'value'")

    category = config.get("category") or input_data.get("category", "Network activity")
    to_ids = bool(config.get("to_ids") or input_data.get("to_ids", True))
    distribution = int(config.get("distribution") or input_data.get("distribution", 0))

    payload = {
        "Attribute": {
            "event_id": str(event_id),
            "type": attribute_type,
            "value": value,
            "category": category,
            "to_ids": to_ids,
            "distribution": distribution,
        }
    }

    log.info("misp.add_attribute", event_id=event_id, type=attribute_type)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"attributes/add/{event_id}", json=payload)
        _raise_for_status(r)
        data = r.json()

    attribute = data.get("Attribute", data)
    return {"attribute": attribute, "attribute_id": attribute.get("id")}


@register_node("misp.search_events")
async def misp_search_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search MISP events using the restSearch endpoint."""
    value = config.get("value") or input_data.get("value")
    attribute_type = config.get("type") or input_data.get("type")
    tags = config.get("tags") or input_data.get("tags")
    from_date = config.get("from") or input_data.get("from")
    to_date = config.get("to") or input_data.get("to")
    limit = int(config.get("limit") or input_data.get("limit", 25))

    payload: dict = {"returnFormat": "json", "limit": limit}
    if value:
        payload["value"] = value
    if attribute_type:
        payload["type"] = attribute_type
    if tags:
        payload["tags"] = tags if isinstance(tags, list) else [tags]
    if from_date:
        payload["from"] = from_date
    if to_date:
        payload["to"] = to_date

    log.info("misp.search_events", value=value, type=attribute_type)
    async with await _client(credential_id, db) as client:
        r = await client.post("events/restSearch", json=payload)
        _raise_for_status(r)
        data = r.json()

    response = data.get("response", data)
    events = response if isinstance(response, list) else response.get("Event", [])
    return {"events": events, "count": len(events)}
