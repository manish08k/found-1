"""iMeetify integration — appointment scheduling."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.imeetify.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("imeetify.get_availability")
async def imeetify_get_availability(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/availability", params={"date": merged.get("date", "")})
        r.raise_for_status()
    return r.json()


@register_node("imeetify.book_appointment")
async def imeetify_book_appointment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/appointments", json={
            "name": merged.get("name", ""),
            "email": merged.get("email", ""),
            "slot_id": merged.get("slot_id", ""),
        })
        r.raise_for_status()
    return r.json()
