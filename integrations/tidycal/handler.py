"""TidyCal — simple booking integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TIDYCAL_BASE = "https://tidycal.com/api"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("tidycal.list_bookings")
async def tidycal_list_bookings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all bookings from TidyCal.

    config:
      api_key — TidyCal API key
    """
    async with httpx.AsyncClient(base_url=TIDYCAL_BASE, timeout=30) as client:
        r = await client.get("/bookings", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    bookings = data.get("data", data if isinstance(data, list) else [])
    log.info("tidycal.list_bookings", count=len(bookings))
    return {"bookings": bookings, "count": len(bookings)}


@register_node("tidycal.list_booking_types")
async def tidycal_list_booking_types(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all booking types from TidyCal.

    config:
      api_key — TidyCal API key
    """
    async with httpx.AsyncClient(base_url=TIDYCAL_BASE, timeout=30) as client:
        r = await client.get("/booking-types", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    booking_types = data.get("data", data if isinstance(data, list) else [])
    log.info("tidycal.list_booking_types", count=len(booking_types))
    return {"booking_types": booking_types, "count": len(booking_types)}


@register_node("tidycal.get_booking")
async def tidycal_get_booking(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single TidyCal booking by ID.

    config/input_data:
      api_key — TidyCal API key
      id      — booking ID (required)
    """
    booking_id = config.get("id") or input_data.get("id")
    if not booking_id:
        raise ValueError("id is required for tidycal.get_booking")

    async with httpx.AsyncClient(base_url=TIDYCAL_BASE, timeout=30) as client:
        r = await client.get(f"/bookings/{booking_id}", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    booking = data.get("data", data)
    log.info("tidycal.get_booking", booking_id=booking_id)
    return {"booking": booking, "id": booking_id}
