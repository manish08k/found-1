"""
MessageAnAgent integration.

Sends a message to an internal AI agent endpoint and returns the response.

Credential fields:
  - api_url : Base URL of the internal agent service
  - api_key : API key for authentication

Config fields:
  - agent_id  : ID of the target agent
  - message   : Message text to send
  - thread_id : (optional) Conversation thread ID for context continuity

Auth: X-Api-Key header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_url = creds.get("api_url", "").rstrip("/")
    api_key = creds.get("api_key")
    if not api_url:
        raise ValueError("MessageAnAgent credential missing 'api_url'")
    if not api_key:
        raise ValueError("MessageAnAgent credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=api_url,
        headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
        timeout=60.0,  # agent calls may be slow
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Agent API error {r.status_code}: {detail}")


@register_node("message_an_agent.send")
async def message_an_agent_send(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a message to an AI agent and return its response.

    Merges config and input_data, with config taking priority.
    """
    agent_id = config.get("agent_id") or input_data.get("agent_id")
    message = config.get("message") or input_data.get("message")
    thread_id = config.get("thread_id") or input_data.get("thread_id")
    extra_context = config.get("context") or input_data.get("context", {})

    if not agent_id:
        raise ValueError("message_an_agent.send requires 'agent_id'")
    if not message:
        raise ValueError("message_an_agent.send requires 'message'")

    payload: dict = {
        "agent_id": agent_id,
        "message": message,
    }
    if thread_id:
        payload["thread_id"] = thread_id
    if extra_context and isinstance(extra_context, dict):
        payload["context"] = extra_context

    log.info("message_an_agent.send", agent_id=agent_id, thread_id=thread_id)
    async with await _client(credential_id, db) as client:
        r = await client.post("/messages", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "response": data.get("response") or data.get("message") or data,
        "thread_id": data.get("thread_id") or thread_id,
        "agent_id": agent_id,
        "metadata": data.get("metadata", {}),
    }
