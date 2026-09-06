"""Azure DevOps integration — projects, work items, repos, and pipelines."""
import base64
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DEVOPS_BASE = "https://dev.azure.com"
API_VERSION = "7.1"


def _devops_headers(pat: str) -> dict:
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _org_url(organization: str) -> str:
    return f"{DEVOPS_BASE}/{organization}"


@register_node("azure_devops.list_projects")
async def azure_devops_list_projects(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all projects in the Azure DevOps organization.

    config:
      organization          — Azure DevOps org name (required)
      personal_access_token — PAT with read access (required)
    """
    merged = {**config, **input_data}
    org = merged.get("organization")
    pat = merged.get("personal_access_token", "")
    if not org:
        raise ValueError("organization is required for azure_devops.list_projects")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_org_url(org)}/_apis/projects",
            headers=_devops_headers(pat),
            params={"api-version": API_VERSION},
        )
        r.raise_for_status()
        data = r.json()

    projects = data.get("value", [])
    log.info("azure_devops.list_projects", org=org, count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("azure_devops.list_work_items")
async def azure_devops_list_work_items(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Query work items in an Azure DevOps project using WIQL.

    config:
      organization          — Azure DevOps org name (required)
      project               — project name or ID (required)
      personal_access_token — PAT (required)
      wiql                  — WIQL query string (optional, defaults to listing all active items)
      top                   — max items to return (optional, default 50)
    """
    merged = {**config, **input_data}
    org = merged.get("organization")
    project = merged.get("project")
    pat = merged.get("personal_access_token", "")
    top = merged.get("top", 50)

    if not org or not project:
        raise ValueError("organization and project are required for azure_devops.list_work_items")

    wiql = merged.get(
        "wiql",
        f"SELECT [System.Id],[System.Title],[System.State] FROM WorkItems WHERE [System.TeamProject] = '{project}' ORDER BY [System.ChangedDate] DESC",
    )

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_org_url(org)}/{project}/_apis/wit/wiql",
            headers=_devops_headers(pat),
            params={"api-version": API_VERSION, "$top": top},
            json={"query": wiql},
        )
        r.raise_for_status()
        query_result = r.json()

    work_item_refs = query_result.get("workItems", [])
    ids = [str(wi["id"]) for wi in work_item_refs]

    work_items: list = []
    if ids:
        async with httpx.AsyncClient(timeout=30) as client:
            r2 = await client.get(
                f"{_org_url(org)}/_apis/wit/workitems",
                headers=_devops_headers(pat),
                params={"ids": ",".join(ids[:200]), "api-version": API_VERSION},
            )
            r2.raise_for_status()
            work_items = r2.json().get("value", [])

    log.info("azure_devops.list_work_items", org=org, project=project, count=len(work_items))
    return {"work_items": work_items, "count": len(work_items)}


@register_node("azure_devops.create_work_item")
async def azure_devops_create_work_item(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Create a work item in an Azure DevOps project.

    config:
      organization          — Azure DevOps org name (required)
      project               — project name (required)
      personal_access_token — PAT with write access (required)
      type                  — work item type e.g. "Task", "Bug", "User Story" (required)
      title                 — title of the work item (required)
      description           — description (optional)
      assigned_to           — email of assignee (optional)
    """
    merged = {**config, **input_data}
    org = merged.get("organization")
    project = merged.get("project")
    pat = merged.get("personal_access_token", "")
    item_type = merged.get("type", "Task")
    title = merged.get("title")

    if not org or not project or not title:
        raise ValueError(
            "organization, project, and title are required for azure_devops.create_work_item"
        )

    patch_doc = [{"op": "add", "path": "/fields/System.Title", "value": title}]
    if merged.get("description"):
        patch_doc.append(
            {"op": "add", "path": "/fields/System.Description", "value": merged["description"]}
        )
    if merged.get("assigned_to"):
        patch_doc.append(
            {"op": "add", "path": "/fields/System.AssignedTo", "value": merged["assigned_to"]}
        )

    headers = _devops_headers(pat)
    headers["Content-Type"] = "application/json-patch+json"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_org_url(org)}/{project}/_apis/wit/workitems/${item_type}",
            headers=headers,
            params={"api-version": API_VERSION},
            json=patch_doc,
        )
        r.raise_for_status()
        item = r.json()

    log.info("azure_devops.create_work_item", work_item_id=item.get("id"), type=item_type)
    return {"work_item": item, "work_item_id": item.get("id")}


@register_node("azure_devops.update_work_item")
async def azure_devops_update_work_item(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Update a work item's fields in Azure DevOps.

    config:
      organization          — Azure DevOps org name (required)
      personal_access_token — PAT (required)
      work_item_id          — ID of the work item (required)
      fields                — dict of field path to value, e.g. {"System.State": "Done"} (required)
    """
    merged = {**config, **input_data}
    org = merged.get("organization")
    pat = merged.get("personal_access_token", "")
    work_item_id = merged.get("work_item_id")
    fields = merged.get("fields", {})

    if not org or not work_item_id:
        raise ValueError(
            "organization and work_item_id are required for azure_devops.update_work_item"
        )
    if not fields:
        raise ValueError("fields dict is required for azure_devops.update_work_item")

    patch_doc = [
        {"op": "add", "path": f"/fields/{key}", "value": value}
        for key, value in fields.items()
    ]

    headers = _devops_headers(pat)
    headers["Content-Type"] = "application/json-patch+json"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(
            f"{_org_url(org)}/_apis/wit/workitems/{work_item_id}",
            headers=headers,
            params={"api-version": API_VERSION},
            json=patch_doc,
        )
        r.raise_for_status()
        item = r.json()

    log.info("azure_devops.update_work_item", work_item_id=work_item_id)
    return {"work_item": item, "work_item_id": work_item_id}


@register_node("azure_devops.list_repos")
async def azure_devops_list_repos(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all Git repositories in an Azure DevOps project.

    config:
      organization          — Azure DevOps org name (required)
      project               — project name (required)
      personal_access_token — PAT (required)
    """
    merged = {**config, **input_data}
    org = merged.get("organization")
    project = merged.get("project")
    pat = merged.get("personal_access_token", "")

    if not org or not project:
        raise ValueError("organization and project are required for azure_devops.list_repos")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_org_url(org)}/{project}/_apis/git/repositories",
            headers=_devops_headers(pat),
            params={"api-version": API_VERSION},
        )
        r.raise_for_status()
        data = r.json()

    repos = data.get("value", [])
    log.info("azure_devops.list_repos", org=org, project=project, count=len(repos))
    return {"repos": repos, "count": len(repos)}


@register_node("azure_devops.list_pipelines")
async def azure_devops_list_pipelines(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all pipelines in an Azure DevOps project.

    config:
      organization          — Azure DevOps org name (required)
      project               — project name (required)
      personal_access_token — PAT (required)
    """
    merged = {**config, **input_data}
    org = merged.get("organization")
    project = merged.get("project")
    pat = merged.get("personal_access_token", "")

    if not org or not project:
        raise ValueError("organization and project are required for azure_devops.list_pipelines")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_org_url(org)}/{project}/_apis/pipelines",
            headers=_devops_headers(pat),
            params={"api-version": API_VERSION},
        )
        r.raise_for_status()
        data = r.json()

    pipelines = data.get("value", [])
    log.info("azure_devops.list_pipelines", org=org, project=project, count=len(pipelines))
    return {"pipelines": pipelines, "count": len(pipelines)}


@register_node("azure_devops.run_pipeline")
async def azure_devops_run_pipeline(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Trigger a run of an Azure DevOps pipeline.

    config:
      organization          — Azure DevOps org name (required)
      project               — project name (required)
      personal_access_token — PAT with Build execute permission (required)
      pipeline_id           — pipeline ID to run (required)
      branch                — branch ref e.g. "refs/heads/main" (optional)
      variables             — dict of variable name to value (optional)
    """
    merged = {**config, **input_data}
    org = merged.get("organization")
    project = merged.get("project")
    pat = merged.get("personal_access_token", "")
    pipeline_id = merged.get("pipeline_id")

    if not org or not project or not pipeline_id:
        raise ValueError(
            "organization, project, and pipeline_id are required for azure_devops.run_pipeline"
        )

    payload: dict = {}
    if merged.get("branch"):
        payload["resources"] = {"repositories": {"self": {"refName": merged["branch"]}}}
    if merged.get("variables"):
        payload["variables"] = {
            k: {"value": v} for k, v in merged["variables"].items()
        }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_org_url(org)}/{project}/_apis/pipelines/{pipeline_id}/runs",
            headers=_devops_headers(pat),
            params={"api-version": API_VERSION},
            json=payload,
        )
        r.raise_for_status()
        run = r.json()

    log.info("azure_devops.run_pipeline", pipeline_id=pipeline_id, run_id=run.get("id"))
    return {"run": run, "run_id": run.get("id"), "pipeline_id": pipeline_id}
