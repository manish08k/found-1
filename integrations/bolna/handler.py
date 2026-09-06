"""Bolna AI voice agent platform integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BOLNA_BASE = "https://api.bolna.dev"


@register_node("bolna.make_call")
async def bolna_make_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Initiate a Bolna AI voice agent call.

    config/input_data:
      api_key       — Bolna API key
      agent_id      — ID of the agent to use
      recipient_phone_number — E.164 phone number to call
      user_data     — optional dict of data to pass to the agent
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    agent_id = merged.get("agent_id", "")
    if not agent_id:
        raise ValueError("agent_id is required")
    recipient_phone_number = merged.get("recipient_phone_number", "")
    if not recipient_phone_number:
        raise ValueError("recipient_phone_number is required")

    payload: dict = {
        "agent_id": agent_id,
        "recipient_phone_number": recipient_phone_number,
    }
    if merged.get("user_data"):
        payload["user_data"] = merged["user_data"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BOLNA_BASE}/call",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("bolna.make_call", agent_id=agent_id)
    return result


@register_node("bolna.get_call")
async def bolna_get_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the status and details of a Bolna call.

    config/input_data:
      api_key    — Bolna API key
      call_id    — ID of the call to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    call_id = merged.get("call_id", "")
    if not call_id:
        raise ValueError("call_id is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BOLNA_BASE}/call/status/{call_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("bolna.get_call", call_id=call_id)
    return result


@register_node("bolna.list_agents")
async def bolna_list_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Bolna AI voice agents.

    config/input_data:
      api_key — Bolna API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BOLNA_BASE}/agent/all",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("bolna.list_agents")
    return result


@register_node("bolna.create_agent")
async def bolna_create_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Bolna AI voice agent.

    config/input_data:
      api_key       — Bolna API key
      agent_name    — name for the agent
      agent_type    — type: IVR, FreeWheeling, etc.
      agent_config  — dict with full agent configuration
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    agent_name = merged.get("agent_name", "")
    if not agent_name:
        raise ValueError("agent_name is required")

    payload: dict = {"agent_name": agent_name}
    if merged.get("agent_type"):
        payload["agent_type"] = merged["agent_type"]
    if merged.get("agent_config"):
        payload["agent_config"] = merged["agent_config"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BOLNA_BASE}/agent",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("bolna.create_agent", agent_name=agent_name)
    return result
