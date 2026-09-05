"""Knock integration — notification infrastructure via Knock API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

KNOCK_BASE = "https://api.knock.app/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_key', '')}"}


@register_node("knock.identify_user")
async def identify_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Identify or update a user in Knock.

    config/input_data:
      api_key — Knock API key (required)
      user_id — User ID (required)
      name    — User's name (optional)
      email   — User's email (optional)
    """
    merged = {**config, **input_data}
    user_id = merged.get("user_id", "")
    if not user_id:
        raise ValueError("user_id is required for knock.identify_user")
    headers = _headers(config, input_data)
    payload = {
        "name": merged.get("name", ""),
        "email": merged.get("email", ""),
    }
    async with httpx.AsyncClient(base_url=KNOCK_BASE, timeout=30) as client:
        r = await client.put(f"/users/{user_id}", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("knock.identify_user", user_id=user_id)
    return {"user": data, "user_id": user_id}


@register_node("knock.trigger_workflow")
async def trigger_workflow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Trigger a Knock notification workflow.

    config/input_data:
      api_key      — Knock API key (required)
      workflow_key — Workflow key to trigger (required)
      recipients   — List of user IDs or recipient objects (required)
      data         — Workflow data dict (optional)
    """
    merged = {**config, **input_data}
    workflow_key = merged.get("workflow_key", "")
    recipients = merged.get("recipients", [])
    if not workflow_key or not recipients:
        raise ValueError("workflow_key and recipients are required for knock.trigger_workflow")
    headers = _headers(config, input_data)
    payload = {"recipients": recipients, "data": merged.get("data", {})}
    async with httpx.AsyncClient(base_url=KNOCK_BASE, timeout=30) as client:
        r = await client.post(f"/workflows/{workflow_key}/trigger", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("knock.trigger_workflow", workflow_key=workflow_key, recipients=len(recipients))
    return {"result": data, "workflow_key": workflow_key}


@register_node("knock.get_user")
async def get_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a user from Knock.

    config/input_data:
      api_key — Knock API key (required)
      user_id — User ID (required)
    """
    merged = {**config, **input_data}
    user_id = merged.get("user_id", "")
    if not user_id:
        raise ValueError("user_id is required for knock.get_user")
    headers = _headers(config, input_data)
    async with httpx.AsyncClient(base_url=KNOCK_BASE, timeout=30) as client:
        r = await client.get(f"/users/{user_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("knock.get_user", user_id=user_id)
    return {"user": data, "user_id": user_id}
