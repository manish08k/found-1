"""Dust AI assistant platform — handler for dust integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://dust.tt/api/v1"


@register_node("dust.create_conversation")
async def dust_create_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a conversation.

    config/input_data:
      api_key — API key or token (required)
      workspace_id — (required)
      message — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workspace_id = merged.get("workspace_id") or ""
    message = merged.get("message") or ""
    if not workspace_id or not message:
        raise ValueError("workspace_id, message required for dust.create_conversation")
    payload = {"message": message}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/w/{workspace_id}/assistant/conversations", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("dust.create_conversation")
    return {"data": data}

@register_node("dust.list_agents")
async def dust_list_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List agents.

    config/input_data:
      api_key — API key or token (required)
      workspace_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workspace_id = merged.get("workspace_id") or ""
    if not workspace_id:
        raise ValueError("workspace_id required for dust.list_agents")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/w/{workspace_id}/assistant/agents", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("dust.list_agents")
    return {"data": data}
