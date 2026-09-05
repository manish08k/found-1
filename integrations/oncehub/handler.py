"""OnceHub — scheduling and booking integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ONCEHUB_BASE = "https://api.oncehub.com/v2"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "API-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("oncehub.list_bookings")
async def oncehub_list_bookings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List bookings from OnceHub.

    config:
      api_key — OnceHub API key
      limit   — number of bookings to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=ONCEHUB_BASE, timeout=30) as client:
        r = await client.get("/bookings", params={"limit": limit}, headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    bookings = data.get("data", data if isinstance(data, list) else [])
    log.info("oncehub.list_bookings", count=len(bookings))
    return {"bookings": bookings, "count": len(bookings)}


@register_node("oncehub.get_booking")
async def oncehub_get_booking(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single OnceHub booking by ID.

    config/input_data:
      api_key — OnceHub API key
      id      — booking ID (required)
    """
    booking_id = config.get("id") or input_data.get("id")
    if not booking_id:
        raise ValueError("id is required for oncehub.get_booking")

    async with httpx.AsyncClient(base_url=ONCEHUB_BASE, timeout=30) as client:
        r = await client.get(f"/bookings/{booking_id}", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    booking = data.get("data", data)
    log.info("oncehub.get_booking", booking_id=booking_id)
    return {"booking": booking, "id": booking_id}


@register_node("oncehub.list_pages")
async def oncehub_list_pages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List booking pages from OnceHub.

    config:
      api_key — OnceHub API key
    """
    async with httpx.AsyncClient(base_url=ONCEHUB_BASE, timeout=30) as client:
        r = await client.get("/booking_pages", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    pages = data.get("data", data if isinstance(data, list) else [])
    log.info("oncehub.list_pages", count=len(pages))
    return {"pages": pages, "count": len(pages)}
