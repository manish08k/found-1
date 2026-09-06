"""Contextual AI RAG agent platform integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CONTEXTUAL_BASE = "https://api.contextual.ai/v1"


@register_node("contextual_ai.query")
async def contextual_ai_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query a Contextual AI agent with a question.

    config/input_data:
      api_key    — Contextual AI API key
      agent_id   — ID of the agent to query
      messages   — list of message dicts with role and content
      stream     — optional bool (default False)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    agent_id = merged.get("agent_id", "")
    if not agent_id:
        raise ValueError("agent_id is required")
    messages = merged.get("messages", [])
    if not messages:
        raise ValueError("messages is required")

    payload = {
        "messages": messages,
        "stream": merged.get("stream", False),
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{CONTEXTUAL_BASE}/agents/{agent_id}/query",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("contextual_ai.query", agent_id=agent_id)
    return result


@register_node("contextual_ai.list_agents")
async def contextual_ai_list_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Contextual AI agents.

    config/input_data:
      api_key — Contextual AI API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{CONTEXTUAL_BASE}/agents",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("contextual_ai.list_agents")
    return result


@register_node("contextual_ai.create_agent")
async def contextual_ai_create_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Contextual AI agent.

    config/input_data:
      api_key             — Contextual AI API key
      name                — agent name
      system_prompt       — optional system prompt for the agent
      datastore_ids       — optional list of datastore IDs to attach
      suggested_queries   — optional list of suggested query strings
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    name = merged.get("name", "")
    if not name:
        raise ValueError("name is required")

    payload: dict = {"name": name}
    if merged.get("system_prompt"):
        payload["system_prompt"] = merged["system_prompt"]
    if merged.get("datastore_ids"):
        payload["datastore_ids"] = merged["datastore_ids"]
    if merged.get("suggested_queries"):
        payload["suggested_queries"] = merged["suggested_queries"]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{CONTEXTUAL_BASE}/agents",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("contextual_ai.create_agent", name=name)
    return result
