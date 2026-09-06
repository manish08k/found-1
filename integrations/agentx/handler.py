"""AgentX AI agent platform — handler for agentx integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.agentx.so/v1"


@register_node("agentx.list_agents")
async def agentx_list_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all AI agents.

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
    log.info("agentx.list_agents")
    return {"data": data}

@register_node("agentx.run_agent")
async def agentx_run_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run an AI agent.

    config/input_data:
      api_key — API key or token (required)
      agent_id — (required)
      input — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    agent_id = merged.get("agent_id") or ""
    input = merged.get("input") or ""
    if not agent_id or not input:
        raise ValueError("agent_id, input required for agentx.run_agent")
    payload = {"input": input}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/agents/{agent_id}/run", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("agentx.run_agent")
    return {"data": data}

@register_node("agentx.get_run")
async def agentx_get_run(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get run status.

    config/input_data:
      api_key — API key or token (required)
      run_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    run_id = merged.get("run_id") or ""
    if not run_id:
        raise ValueError("run_id required for agentx.get_run")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/runs/{run_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("agentx.get_run")
    return {"data": data}
