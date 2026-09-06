"""Comet ML experiment tracking — handler for cometapi integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.comet.com/api/rest/v2"


@register_node("cometapi.list_experiments")
async def cometapi_list_experiments(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List experiments.

    config/input_data:
      api_key — API key or token (required)
      workspace — (required)
      project_name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workspace = merged.get("workspace") or ""
    project_name = merged.get("project_name") or ""
    if not workspace or not project_name:
        raise ValueError("workspace, project_name required for cometapi.list_experiments")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/experiments", headers=headers, params={"workspace": workspace, "project_name": project_name})
        r.raise_for_status()
        data = r.json()
    log.info("cometapi.list_experiments")
    return {"data": data}

@register_node("cometapi.get_experiment")
async def cometapi_get_experiment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get experiment details.

    config/input_data:
      api_key — API key or token (required)
      experiment_key — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    experiment_key = merged.get("experiment_key") or ""
    if not experiment_key:
        raise ValueError("experiment_key required for cometapi.get_experiment")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/experiments/{experiment_key}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("cometapi.get_experiment")
    return {"data": data}

@register_node("cometapi.list_projects")
async def cometapi_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects.

    config/input_data:
      api_key — API key or token (required)
      workspace — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    workspace = merged.get("workspace") or ""
    if not workspace:
        raise ValueError("workspace required for cometapi.list_projects")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/projects", headers=headers, params={"workspace": workspace})
        r.raise_for_status()
        data = r.json()
    log.info("cometapi.list_projects")
    return {"data": data}
