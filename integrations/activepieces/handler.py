"""Activepieces workflow automation platform — handler for activepieces integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://cloud.activepieces.com/api/v1"


@register_node("activepieces.list_flows")
async def activepieces_list_flows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all flows.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/flows", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("activepieces.list_flows")
    return {"data": data}

@register_node("activepieces.get_flow")
async def activepieces_get_flow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific flow.

    config/input_data:
      api_key — API key or token (required)
      flow_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    flow_id = merged.get("flow_id") or ""
    if not flow_id:
        raise ValueError("flow_id required for activepieces.get_flow")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/flows/{flow_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("activepieces.get_flow")
    return {"data": data}

@register_node("activepieces.list_connections")
async def activepieces_list_connections(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all connections.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/connections", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("activepieces.list_connections")
    return {"data": data}
