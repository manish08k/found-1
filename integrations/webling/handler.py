"""Webling member management for associations — handler for webling integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL_TEMPLATE = "https://{domain}.webling.ch/api/1"


def _build_base_url(merged: dict) -> str:
    domain = merged.get("domain") or merged.get("subdomain") or ""
    if not domain:
        raise ValueError("domain (subdomain) is required for webling operations")
    return BASE_URL_TEMPLATE.format(domain=domain)


@register_node("webling.list_members")
async def webling_list_members(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List members.

    config/input_data:
      domain / subdomain — Webling domain (required)
      api_key — API key (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/member", headers=headers, params={"apikey": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("webling.list_members")
    return {"data": data}

@register_node("webling.get_member")
async def webling_get_member(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get member details.

    config/input_data:
      domain / subdomain — Webling domain (required)
      api_key — API key (required)
      member_id — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    member_id = merged.get("member_id") or ""
    if not member_id:
        raise ValueError("member_id required for webling.get_member")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/member/{member_id}", headers=headers, params={"apikey": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("webling.get_member")
    return {"data": data}

@register_node("webling.create_member")
async def webling_create_member(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a member.

    config/input_data:
      domain / subdomain — Webling domain (required)
      api_key — API key (required)
      properties — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    properties = merged.get("properties") or ""
    if not properties:
        raise ValueError("properties required for webling.create_member")
    payload = {"properties": properties}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/member", headers=headers, json=payload, params={"apikey": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("webling.create_member")
    return {"data": data}
