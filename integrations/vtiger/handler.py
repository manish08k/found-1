"""Vtiger CRM platform — handler for vtiger integration."""
import base64

import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL_TEMPLATE = "https://{instance}.vtiger.com/restapi/v1/vtiger/default"


def _build_base_url(merged: dict) -> str:
    instance = merged.get("instance") or merged.get("subdomain") or ""
    if not instance:
        raise ValueError("instance (subdomain) is required for vtiger operations")
    return BASE_URL_TEMPLATE.format(instance=instance)


def _build_headers(merged: dict) -> dict:
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


@register_node("vtiger.list_records")
async def vtiger_list_records(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query records.

    config/input_data:
      instance — Vtiger subdomain (required)
      username / api_key — (required)
      password / api_token — (required)
      query — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    query = merged.get("query") or ""
    if not query:
        raise ValueError("query required for vtiger.list_records")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/query", headers=headers, params={"query": query})
        r.raise_for_status()
        data = r.json()
    log.info("vtiger.list_records")
    return {"data": data}

@register_node("vtiger.create_record")
async def vtiger_create_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a record.

    config/input_data:
      instance — Vtiger subdomain (required)
      username / api_key — (required)
      password / api_token — (required)
      elementType — (required)
      element — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    elementType = merged.get("elementType") or ""
    element = merged.get("element") or ""
    if not elementType or not element:
        raise ValueError("elementType, element required for vtiger.create_record")
    payload = {"elementType": elementType, "element": element}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/create", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("vtiger.create_record")
    return {"data": data}

@register_node("vtiger.get_record")
async def vtiger_get_record(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve a record.

    config/input_data:
      instance — Vtiger subdomain (required)
      username / api_key — (required)
      password / api_token — (required)
      id — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    record_id = merged.get("id") or ""
    if not record_id:
        raise ValueError("id required for vtiger.get_record")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/retrieve", headers=headers, params={"id": record_id})
        r.raise_for_status()
        data = r.json()
    log.info("vtiger.get_record")
    return {"data": data}
