"""Vercel integration — deployments and projects."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

VERCEL_BASE = "https://api.vercel.com"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("vercel.list_deployments")
async def vercel_list_deployments(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Vercel deployments.

    config:
      api_key — Vercel API token (required)
      limit   — Number of deployments (default 20)
      team_id — Team ID (optional)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for vercel.list_deployments")
    limit = int(config.get("limit", 20))

    params: dict = {"limit": limit}
    team_id = config.get("team_id") or input_data.get("team_id")
    if team_id:
        params["teamId"] = team_id

    async with httpx.AsyncClient(base_url=VERCEL_BASE, timeout=30) as client:
        r = await client.get("/v6/deployments", headers=_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    deployments = data.get("deployments", [])
    log.info("vercel.list_deployments", count=len(deployments))
    return {"deployments": deployments, "count": len(deployments), "pagination": data.get("pagination", {})}


@register_node("vercel.get_deployment")
async def vercel_get_deployment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a Vercel deployment by ID.

    config/input_data:
      api_key — Vercel API token (required)
      id      — Deployment ID or URL (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    deployment_id = config.get("id") or input_data.get("id")

    if not api_key:
        raise ValueError("api_key is required for vercel.get_deployment")
    if not deployment_id:
        raise ValueError("id is required for vercel.get_deployment")

    async with httpx.AsyncClient(base_url=VERCEL_BASE, timeout=30) as client:
        r = await client.get(f"/v13/deployments/{deployment_id}", headers=_headers(api_key))
        r.raise_for_status()
        deployment = r.json()

    log.info("vercel.get_deployment", deployment_id=deployment_id, state=deployment.get("readyState"))
    return {"deployment": deployment, "id": deployment_id, "state": deployment.get("readyState"), "url": deployment.get("url")}


@register_node("vercel.list_projects")
async def vercel_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Vercel projects.

    config:
      api_key — Vercel API token (required)
      limit   — Number of projects (default 20)
      team_id — Team ID (optional)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for vercel.list_projects")
    limit = int(config.get("limit", 20))

    params: dict = {"limit": limit}
    team_id = config.get("team_id") or input_data.get("team_id")
    if team_id:
        params["teamId"] = team_id

    async with httpx.AsyncClient(base_url=VERCEL_BASE, timeout=30) as client:
        r = await client.get("/v9/projects", headers=_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    projects = data.get("projects", [])
    log.info("vercel.list_projects", count=len(projects))
    return {"projects": projects, "count": len(projects), "pagination": data.get("pagination", {})}


@register_node("vercel.create_deployment")
async def vercel_create_deployment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Vercel deployment.

    config/input_data:
      api_key      — Vercel API token (required)
      project_name — Project name (required)
      target       — Deployment target "production" or "preview" (default "production")
      team_id      — Team ID (optional)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    project_name = config.get("project_name") or input_data.get("project_name")

    if not api_key:
        raise ValueError("api_key is required for vercel.create_deployment")
    if not project_name:
        raise ValueError("project_name is required for vercel.create_deployment")

    target = config.get("target", "production")
    payload: dict = {"name": project_name, "target": target}

    params: dict = {}
    team_id = config.get("team_id") or input_data.get("team_id")
    if team_id:
        params["teamId"] = team_id

    async with httpx.AsyncClient(base_url=VERCEL_BASE, timeout=30) as client:
        r = await client.post("/v13/deployments", headers=_headers(api_key), json=payload, params=params)
        r.raise_for_status()
        deployment = r.json()

    log.info("vercel.create_deployment", project_name=project_name, deployment_id=deployment.get("id"), state=deployment.get("readyState"))
    return {"deployment": deployment, "id": deployment.get("id"), "state": deployment.get("readyState"), "url": deployment.get("url")}
