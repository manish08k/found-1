"""Simpliroute route optimization and delivery tracking integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.simpliroute.com/v1"


@register_node("simpliroute.optimize_route")
async def simpliroute_optimize_route(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Optimize a delivery route."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    payload = {
        "visits": merged.get("visits", []),
        "vehicle": merged.get("vehicle", {}),
        "depot": merged.get("depot", {}),
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE_URL}/routes/optimize/",
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()
    log.info("simpliroute.optimize_route")
    return result


@register_node("simpliroute.list_routes")
async def simpliroute_list_routes(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all routes."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/routes/",
            headers={"Authorization": f"Token {api_key}"},
            params={"page": merged.get("page", 1), "page_size": merged.get("page_size", 20)},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simpliroute.list_routes")
    return result


@register_node("simpliroute.create_delivery")
async def simpliroute_create_delivery(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a delivery visit."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    payload = {
        "title": merged.get("title", ""),
        "address": merged.get("address", ""),
        "lat": merged.get("lat"),
        "lng": merged.get("lng"),
        "notes": merged.get("notes", ""),
        "contact_name": merged.get("contact_name", ""),
        "contact_phone": merged.get("contact_phone", ""),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/visits/",
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            json={k: v for k, v in payload.items() if v is not None},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simpliroute.create_delivery")
    return result


@register_node("simpliroute.track_delivery")
async def simpliroute_track_delivery(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track a delivery visit by ID."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    visit_id = merged.get("visit_id", "")
    if not visit_id:
        raise ValueError("visit_id is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/visits/{visit_id}/",
            headers={"Authorization": f"Token {api_key}"},
        )
        r.raise_for_status()
        result = r.json()
    log.info("simpliroute.track_delivery")
    return result
