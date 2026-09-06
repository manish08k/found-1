"""WhatConverts lead tracking and reporting — handler for what_converts integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://app.whatconverts.com/api/v1"


@register_node("what_converts.list_leads")
async def what_converts_list_leads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List leads.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/leads", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("what_converts.list_leads")
    return {"data": data}

@register_node("what_converts.get_lead")
async def what_converts_get_lead(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get lead details.

    config/input_data:
      api_key — API key or token (required)
      lead_id — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    lead_id = merged.get("lead_id") or ""
    if not lead_id:
        raise ValueError("lead_id required for what_converts.get_lead")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/leads/{lead_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("what_converts.get_lead")
    return {"data": data}

@register_node("what_converts.list_accounts")
async def what_converts_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List accounts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/accounts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("what_converts.list_accounts")
    return {"data": data}
