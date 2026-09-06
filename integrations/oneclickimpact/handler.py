"""OneClickImpact donation and impact platform — handler for oneclickimpact integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.oneclickimpact.com/v1"


@register_node("oneclickimpact.create_donation")
async def oneclickimpact_create_donation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a donation.

    config/input_data:
      api_key — API key or token (required)
      amount — (required)
      project_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    amount = merged.get("amount") or ""
    project_id = merged.get("project_id") or ""
    if not amount or not project_id:
        raise ValueError("amount, project_id required for oneclickimpact.create_donation")
    payload = {"amount": amount, "project_id": project_id}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/donations", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("oneclickimpact.create_donation")
    return {"data": data}

@register_node("oneclickimpact.list_projects")
async def oneclickimpact_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/projects", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("oneclickimpact.list_projects")
    return {"data": data}

@register_node("oneclickimpact.get_impact")
async def oneclickimpact_get_impact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get impact metrics.

    config/input_data:
      api_key — API key or token (required)
      project_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    project_id = merged.get("project_id") or ""
    if not project_id:
        raise ValueError("project_id required for oneclickimpact.get_impact")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/impact/{project_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("oneclickimpact.get_impact")
    return {"data": data}
