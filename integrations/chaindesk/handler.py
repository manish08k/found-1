"""Chaindesk AI chatbot platform — handler for chaindesk integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.chaindesk.ai/v1"


@register_node("chaindesk.query_agent")
async def chaindesk_query_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query an AI agent.

    config/input_data:
      api_key — API key or token (required)
      agent_id — (required)
      query — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    agent_id = merged.get("agent_id") or ""
    query = merged.get("query") or ""
    if not agent_id or not query:
        raise ValueError("agent_id, query required for chaindesk.query_agent")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/agents/{agent_id}/query", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("chaindesk.query_agent")
    return {"data": data}

@register_node("chaindesk.list_agents")
async def chaindesk_list_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List AI agents.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/agents", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chaindesk.list_agents")
    return {"data": data}

@register_node("chaindesk.list_datastores")
async def chaindesk_list_datastores(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List datastores.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/datastores", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("chaindesk.list_datastores")
    return {"data": data}
