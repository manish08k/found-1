"""Campaign Monitor integration — email marketing via Campaign Monitor API v3.3."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CM_BASE = "https://api.createsend.com/api/v3.3"


def _auth(config: dict, input_data: dict) -> tuple:
    """Return (api_key,) for HTTP Basic auth — api_key is the username, password empty."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    return (api_key, "")


@register_node("campaign_monitor.list_clients")
async def list_clients(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all clients in the Campaign Monitor account.

    config/input_data:
      api_key — Campaign Monitor API key (required)
    """
    auth = _auth(config, input_data)
    async with httpx.AsyncClient(base_url=CM_BASE, timeout=30) as client:
        r = await client.get("/clients.json", auth=auth)
        r.raise_for_status()
        data = r.json()
    log.info("campaign_monitor.list_clients", count=len(data))
    return {"clients": data, "count": len(data)}


@register_node("campaign_monitor.list_campaigns")
async def list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all sent campaigns for a client.

    config/input_data:
      api_key   — Campaign Monitor API key (required)
      client_id — Client ID to list campaigns for (required)
    """
    merged = {**config, **input_data}
    client_id = merged.get("client_id", "")
    if not client_id:
        raise ValueError("client_id is required for campaign_monitor.list_campaigns")
    auth = _auth(config, input_data)
    async with httpx.AsyncClient(base_url=CM_BASE, timeout=30) as client:
        r = await client.get(f"/clients/{client_id}/campaigns.json", auth=auth)
        r.raise_for_status()
        data = r.json()
    log.info("campaign_monitor.list_campaigns", client_id=client_id, count=len(data))
    return {"campaigns": data, "count": len(data), "client_id": client_id}


@register_node("campaign_monitor.list_subscribers")
async def list_subscribers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List active subscribers in a list.

    config/input_data:
      api_key  — Campaign Monitor API key (required)
      list_id  — Subscriber list ID (required)
    """
    merged = {**config, **input_data}
    list_id = merged.get("list_id", "")
    if not list_id:
        raise ValueError("list_id is required for campaign_monitor.list_subscribers")
    auth = _auth(config, input_data)
    async with httpx.AsyncClient(base_url=CM_BASE, timeout=30) as client:
        r = await client.get(
            f"/lists/{list_id}/active.json",
            params={"page": 1, "pagesize": 100},
            auth=auth,
        )
        r.raise_for_status()
        data = r.json()
    results = data.get("Results", [])
    log.info("campaign_monitor.list_subscribers", list_id=list_id, count=len(results))
    return {"subscribers": results, "count": len(results), "list_id": list_id}


@register_node("campaign_monitor.add_subscriber")
async def add_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add or resubscribe a subscriber to a list.

    config/input_data:
      api_key  — Campaign Monitor API key (required)
      list_id  — Subscriber list ID (required)
      email    — Email address (required)
      name     — Subscriber's name (optional)
    """
    merged = {**config, **input_data}
    list_id = merged.get("list_id", "")
    email = merged.get("email", "")
    name = merged.get("name", "")
    if not list_id or not email:
        raise ValueError("list_id and email are required for campaign_monitor.add_subscriber")
    auth = _auth(config, input_data)
    payload = {"EmailAddress": email, "Name": name, "Resubscribe": True}
    async with httpx.AsyncClient(base_url=CM_BASE, timeout=30) as client:
        r = await client.post(f"/subscribers/{list_id}.json", json=payload, auth=auth)
        r.raise_for_status()
        data = r.json()
    log.info("campaign_monitor.add_subscriber", list_id=list_id, email=email)
    return {"result": data, "email": email, "list_id": list_id}
