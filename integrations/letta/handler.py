"""Letta (MemGPT) — AI agent memory and messaging integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

_DEFAULT_BASE = "https://api.letta.ai/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _base_url(config: dict) -> str:
    return config.get("base_url", _DEFAULT_BASE).rstrip("/")


@register_node("letta.list_agents")
async def letta_list_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Letta AI agents.

    config:
      api_key  — Letta API key
      base_url — optional self-hosted base URL (default: https://api.letta.ai/v1)
    """
    base_url = _base_url(config)

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.get("/agents", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    agents = data if isinstance(data, list) else data.get("agents", [])
    log.info("letta.list_agents", count=len(agents))
    return {"agents": agents, "count": len(agents)}


@register_node("letta.create_agent")
async def letta_create_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Letta AI agent.

    config/input_data:
      api_key  — Letta API key
      base_url — optional self-hosted base URL
      name     — agent name (required)
      persona  — persona text for the agent's memory (optional)
    """
    name = config.get("name") or input_data.get("name")
    persona = config.get("persona") or input_data.get("persona", "")
    base_url = _base_url(config)

    if not name:
        raise ValueError("name is required for letta.create_agent")

    payload = {
        "name": name,
        "memory": {
            "human": "",
            "persona": persona,
        },
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.post("/agents", json=payload, headers=_headers(config))
        r.raise_for_status()
        agent = r.json()

    log.info("letta.create_agent", name=name, agent_id=agent.get("id"))
    return {"agent": agent, "id": agent.get("id"), "name": name}


@register_node("letta.send_message")
async def letta_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a Letta AI agent.

    config/input_data:
      api_key  — Letta API key
      base_url — optional self-hosted base URL
      agent_id — target agent ID (required)
      text     — message text to send (required)
    """
    agent_id = config.get("agent_id") or input_data.get("agent_id")
    text = config.get("text") or input_data.get("text")
    base_url = _base_url(config)

    if not agent_id:
        raise ValueError("agent_id is required for letta.send_message")
    if not text:
        raise ValueError("text is required for letta.send_message")

    payload = {
        "messages": [{"role": "user", "content": text}],
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        r = await client.post(
            f"/agents/{agent_id}/messages",
            json=payload,
            headers=_headers(config),
        )
        r.raise_for_status()
        result = r.json()

    messages = result.get("messages", result if isinstance(result, list) else [])
    log.info("letta.send_message", agent_id=agent_id, reply_count=len(messages))
    return {"messages": messages, "agent_id": agent_id, "raw": result}


@register_node("letta.get_agent_memory")
async def letta_get_agent_memory(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve the current memory state of a Letta AI agent.

    config/input_data:
      api_key  — Letta API key
      base_url — optional self-hosted base URL
      agent_id — agent ID to retrieve memory for (required)
    """
    agent_id = config.get("agent_id") or input_data.get("agent_id")
    base_url = _base_url(config)

    if not agent_id:
        raise ValueError("agent_id is required for letta.get_agent_memory")

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.get(f"/agents/{agent_id}/memory", headers=_headers(config))
        r.raise_for_status()
        memory = r.json()

    log.info("letta.get_agent_memory", agent_id=agent_id)
    return {"memory": memory, "agent_id": agent_id}
