"""beehiiv integration — newsletter platform via beehiiv API v2."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BEEHIIV_BASE = "https://api.beehiiv.com/v2"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("beehiv.list_publications")
async def list_publications(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all publications in beehiiv.

    config/input_data:
      api_key — beehiiv API key (required)
    """
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=BEEHIIV_BASE, timeout=30) as client:
        r = await client.get("/publications", headers=headers)
        r.raise_for_status()
        data = r.json()
    publications = data.get("data", [])
    log.info("beehiv.list_publications", count=len(publications))
    return {"publications": publications, "count": len(publications)}


@register_node("beehiv.list_subscribers")
async def list_subscribers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscribers for a publication.

    config/input_data:
      api_key — beehiiv API key (required)
      pub_id  — Publication ID (required)
    """
    merged = {**config, **input_data}
    pub_id = merged.get("pub_id", "")
    if not pub_id:
        raise ValueError("pub_id is required for beehiv.list_subscribers")
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=BEEHIIV_BASE, timeout=30) as client:
        r = await client.get(
            f"/publications/{pub_id}/subscriptions",
            params={"limit": 25},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
    subscribers = data.get("data", [])
    log.info("beehiv.list_subscribers", pub_id=pub_id, count=len(subscribers))
    return {"subscribers": subscribers, "count": len(subscribers), "pub_id": pub_id}


@register_node("beehiv.create_subscriber")
async def create_subscriber(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a subscription for a publication in beehiiv.

    config/input_data:
      api_key            — beehiiv API key (required)
      pub_id             — Publication ID (required)
      email              — Subscriber email (required)
      reactivate_existing — Reactivate if already subscribed (default False)
      send_welcome_email — Send welcome email (default False)
    """
    merged = {**config, **input_data}
    pub_id = merged.get("pub_id", "")
    email = merged.get("email", "")
    if not pub_id or not email:
        raise ValueError("pub_id and email are required for beehiv.create_subscriber")
    headers = _headers(config, input_data)
    payload = {
        "email": email,
        "reactivate_existing": bool(merged.get("reactivate_existing", False)),
        "send_welcome_email": bool(merged.get("send_welcome_email", False)),
    }
    async with httpx.AsyncClient(base_url=BEEHIIV_BASE, timeout=30) as client:
        r = await client.post(f"/publications/{pub_id}/subscriptions", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("beehiv.create_subscriber", pub_id=pub_id, email=email)
    return {"subscriber": data.get("data", data), "email": email, "pub_id": pub_id}
