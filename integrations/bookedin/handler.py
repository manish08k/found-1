"""Bookedin — online booking integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BOOKEDIN_BASE = "https://app.bookedin.com/api"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("bookedin.list_appointments")
async def bookedin_list_appointments(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List appointments from Bookedin.

    config:
      api_key — Bookedin API key
      limit   — number of appointments to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=BOOKEDIN_BASE, timeout=30) as client:
        r = await client.get("/appointments", params={"limit": limit}, headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    appointments = data.get("data", data if isinstance(data, list) else [])
    log.info("bookedin.list_appointments", count=len(appointments))
    return {"appointments": appointments, "count": len(appointments)}


@register_node("bookedin.get_appointment")
async def bookedin_get_appointment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Bookedin appointment by ID.

    config/input_data:
      api_key — Bookedin API key
      id      — appointment ID (required)
    """
    appointment_id = config.get("id") or input_data.get("id")
    if not appointment_id:
        raise ValueError("id is required for bookedin.get_appointment")

    async with httpx.AsyncClient(base_url=BOOKEDIN_BASE, timeout=30) as client:
        r = await client.get(f"/appointments/{appointment_id}", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    appointment = data.get("data", data)
    log.info("bookedin.get_appointment", appointment_id=appointment_id)
    return {"appointment": appointment, "id": appointment_id}
