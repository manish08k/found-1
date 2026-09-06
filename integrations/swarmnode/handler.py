"""SwarmNode integration — distributed AI agent orchestration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.swarmnode.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("swarmnode.create_agent")
async def swarmnode_create_agent(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/agents", json={
            "name": merged.get("name", ""),
            "script": merged.get("script", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("swarmnode.execute_agent")
async def swarmnode_execute_agent(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    agent_id = merged.get("agent_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/agents/{agent_id}/executions", json={"payload": merged.get("payload", {})})
        r.raise_for_status()
    return r.json()


@register_node("swarmnode.get_execution")
async def swarmnode_get_execution(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    execution_id = merged.get("execution_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/executions/{execution_id}")
        r.raise_for_status()
    return r.json()
