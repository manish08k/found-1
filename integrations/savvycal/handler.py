"""SavvyCal — scheduling integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SAVVYCAL_BASE = "https://savvycal.com/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("savvycal.list_links")
async def savvycal_list_links(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List scheduling links from SavvyCal.

    config:
      api_key — SavvyCal API key
    """
    async with httpx.AsyncClient(base_url=SAVVYCAL_BASE, timeout=30) as client:
        r = await client.get("/links", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    links = data.get("data", data if isinstance(data, list) else [])
    log.info("savvycal.list_links", count=len(links))
    return {"links": links, "count": len(links)}


@register_node("savvycal.list_events")
async def savvycal_list_events(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List scheduled events from SavvyCal.

    config:
      api_key — SavvyCal API key
      limit   — number of events to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=SAVVYCAL_BASE, timeout=30) as client:
        r = await client.get("/events", params={"limit": limit}, headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    events = data.get("data", data if isinstance(data, list) else [])
    log.info("savvycal.list_events", count=len(events))
    return {"events": events, "count": len(events)}


@register_node("savvycal.get_event")
async def savvycal_get_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single SavvyCal event by ID.

    config/input_data:
      api_key — SavvyCal API key
      id      — event ID (required)
    """
    event_id = config.get("id") or input_data.get("id")
    if not event_id:
        raise ValueError("id is required for savvycal.get_event")

    async with httpx.AsyncClient(base_url=SAVVYCAL_BASE, timeout=30) as client:
        r = await client.get(f"/events/{event_id}", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    event = data.get("data", data)
    log.info("savvycal.get_event", event_id=event_id)
    return {"event": event, "id": event_id}
