"""Zeplin design handoff and collaboration — handler for zeplin integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.zeplin.dev/v1"


@register_node("zeplin.list_projects")
async def zeplin_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
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
    log.info("zeplin.list_projects")
    return {"data": data}

@register_node("zeplin.get_project")
async def zeplin_get_project(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get project details.

    config/input_data:
      api_key — API key or token (required)
      project_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    project_id = merged.get("project_id") or ""
    if not project_id:
        raise ValueError("project_id required for zeplin.get_project")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zeplin.get_project")
    return {"data": data}

@register_node("zeplin.list_screens")
async def zeplin_list_screens(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List screens in a project.

    config/input_data:
      api_key — API key or token (required)
      project_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    project_id = merged.get("project_id") or ""
    if not project_id:
        raise ValueError("project_id required for zeplin.list_screens")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/projects/{project_id}/screens", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zeplin.list_screens")
    return {"data": data}
