"""Bumpups video repurposing platform — handler for bumpups integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bumpups.com/v1"


@register_node("bumpups.create_project")
async def bumpups_create_project(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a project from a video.

    config/input_data:
      api_key — API key or token (required)
      video_url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    video_url = merged.get("video_url") or ""
    if not video_url:
        raise ValueError("video_url required for bumpups.create_project")
    payload = {"video_url": video_url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/projects", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("bumpups.create_project")
    return {"data": data}

@register_node("bumpups.get_project")
async def bumpups_get_project(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get project status.

    config/input_data:
      api_key — API key or token (required)
      project_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    project_id = merged.get("project_id") or ""
    if not project_id:
        raise ValueError("project_id required for bumpups.get_project")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/projects/{project_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("bumpups.get_project")
    return {"data": data}

@register_node("bumpups.list_projects")
async def bumpups_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all projects.

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
    log.info("bumpups.list_projects")
    return {"data": data}
