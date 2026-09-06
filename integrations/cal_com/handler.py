"""Cal.com open scheduling platform — handler for cal_com integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.cal.com/v1"


@register_node("cal_com.list_event_types")
async def cal_com_list_event_types(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List event types.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: apiKey
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/event-types", headers=headers, params={"apiKey": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("cal_com.list_event_types")
    return {"data": data}

@register_node("cal_com.list_bookings")
async def cal_com_list_bookings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List bookings.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: apiKey
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/bookings", headers=headers, params={"apiKey": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("cal_com.list_bookings")
    return {"data": data}

@register_node("cal_com.create_booking")
async def cal_com_create_booking(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a booking.

    config/input_data:
      api_key — API key or token (required)
      eventTypeId — (required)
      start — (required)
      responses — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: apiKey
    eventTypeId = merged.get("eventTypeId") or ""
    start = merged.get("start") or ""
    responses = merged.get("responses") or ""
    if not eventTypeId or not start or not responses:
        raise ValueError("eventTypeId, start, responses required for cal_com.create_booking")
    payload = {"eventTypeId": eventTypeId, "start": start, "responses": responses}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/bookings", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("cal_com.create_booking")
    return {"data": data}

@register_node("cal_com.cancel_booking")
async def cal_com_cancel_booking(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Cancel a booking.

    config/input_data:
      api_key — API key or token (required)
      booking_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: apiKey
    booking_id = merged.get("booking_id") or ""
    if not booking_id:
        raise ValueError("booking_id required for cal_com.cancel_booking")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BASE_URL}/bookings/{booking_id}/cancel", headers=headers)
        r.raise_for_status()
    log.info("cal_com.cancel_booking")
    return {"ok": True}
