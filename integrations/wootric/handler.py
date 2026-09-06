"""Wootric NPS and customer feedback — handler for wootric integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.wootric.com/v1"


@register_node("wootric.list_responses")
async def wootric_list_responses(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List survey responses.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/responses", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("wootric.list_responses")
    return {"data": data}

@register_node("wootric.create_end_user")
async def wootric_create_end_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an end user.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    email = merged.get("email") or ""
    if not email:
        raise ValueError("email required for wootric.create_end_user")
    payload = {"email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/end_users", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("wootric.create_end_user")
    return {"data": data}

@register_node("wootric.get_end_user")
async def wootric_get_end_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get end user details.

    config/input_data:
      api_key — API key or token (required)
      user_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    user_id = merged.get("user_id") or ""
    if not user_id:
        raise ValueError("user_id required for wootric.get_end_user")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/end_users/{user_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("wootric.get_end_user")
    return {"data": data}
