"""AMPECO EV charging management platform — handler for ampeco integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.ampeco.com/v1"


@register_node("ampeco.list_charge_points")
async def ampeco_list_charge_points(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List charge points.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/charge-points", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("ampeco.list_charge_points")
    return {"data": data}

@register_node("ampeco.get_charge_point")
async def ampeco_get_charge_point(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get charge point details.

    config/input_data:
      api_key — API key or token (required)
      cp_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    cp_id = merged.get("cp_id") or ""
    if not cp_id:
        raise ValueError("cp_id required for ampeco.get_charge_point")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/charge-points/{cp_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("ampeco.get_charge_point")
    return {"data": data}

@register_node("ampeco.start_charging")
async def ampeco_start_charging(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Start a charging session.

    config/input_data:
      api_key — API key or token (required)
      cp_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    cp_id = merged.get("cp_id") or ""
    if not cp_id:
        raise ValueError("cp_id required for ampeco.start_charging")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/charge-points/{cp_id}/start", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("ampeco.start_charging")
    return {"data": data}

@register_node("ampeco.stop_charging")
async def ampeco_stop_charging(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Stop a charging session.

    config/input_data:
      api_key — API key or token (required)
      cp_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    cp_id = merged.get("cp_id") or ""
    if not cp_id:
        raise ValueError("cp_id required for ampeco.stop_charging")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/charge-points/{cp_id}/stop", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("ampeco.stop_charging")
    return {"data": data}
