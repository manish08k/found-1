"""YouCanBookMe online scheduling — handler for youcanbookme integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.youcanbook.me/v1"


@register_node("youcanbookme.list_profiles")
async def youcanbookme_list_profiles(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List booking profiles.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/profiles", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("youcanbookme.list_profiles")
    return {"data": data}

@register_node("youcanbookme.list_bookings")
async def youcanbookme_list_bookings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List bookings.

    config/input_data:
      api_key — API key or token (required)
      profile_id — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    profile_id = merged.get("profile_id") or ""
    if not profile_id:
        raise ValueError("profile_id required for youcanbookme.list_bookings")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/profiles/{profile_id}/bookings", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("youcanbookme.list_bookings")
    return {"data": data}

@register_node("youcanbookme.get_booking")
async def youcanbookme_get_booking(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get booking details.

    config/input_data:
      api_key — API key or token (required)
      profile_id — (required)
      booking_id — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    profile_id = merged.get("profile_id") or ""
    booking_id = merged.get("booking_id") or ""
    if not profile_id or not booking_id:
        raise ValueError("profile_id, booking_id required for youcanbookme.get_booking")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/profiles/{profile_id}/bookings/{booking_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("youcanbookme.get_booking")
    return {"data": data}
