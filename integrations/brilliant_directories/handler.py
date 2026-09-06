"""Brilliant Directories membership site builder — handler for brilliant_directories integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.brilliantdirectories.com/v1"


@register_node("brilliant_directories.list_members")
async def brilliant_directories_list_members(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List members.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/members", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("brilliant_directories.list_members")
    return {"data": data}

@register_node("brilliant_directories.create_member")
async def brilliant_directories_create_member(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a member.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    email = merged.get("email") or ""
    name = merged.get("name") or ""
    if not email or not name:
        raise ValueError("email, name required for brilliant_directories.create_member")
    payload = {"email": email, "name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/members", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("brilliant_directories.create_member")
    return {"data": data}

@register_node("brilliant_directories.get_member")
async def brilliant_directories_get_member(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get member details.

    config/input_data:
      api_key — API key or token (required)
      member_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    member_id = merged.get("member_id") or ""
    if not member_id:
        raise ValueError("member_id required for brilliant_directories.get_member")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/members/{member_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("brilliant_directories.get_member")
    return {"data": data}
