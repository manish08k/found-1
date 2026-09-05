"""YouTrack issue tracker integration — issues and projects."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_url(instance: str) -> str:
    return f"https://{instance}.youtrack.cloud/api"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("youtrack.list_issues")
async def youtrack_list_issues(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List YouTrack issues with key fields.

    config:
      api_key  — YouTrack permanent token (required)
      instance — YouTrack cloud instance subdomain, e.g. "myteam" (required)
      top      — max number of issues to return (default 25)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    instance = config.get("instance") or input_data.get("instance")
    if not api_key or not instance:
        raise ValueError("api_key and instance are required for youtrack.list_issues")

    top = int(config.get("top", 25))

    async with httpx.AsyncClient(base_url=_base_url(instance), timeout=30) as client:
        r = await client.get(
            "/issues",
            params={"fields": "id,summary,description", "$top": top},
            headers=_headers(api_key),
        )
        r.raise_for_status()
        issues = r.json()

    log.info("youtrack.list_issues", instance=instance, count=len(issues))
    return {"issues": issues, "count": len(issues)}


@register_node("youtrack.create_issue")
async def youtrack_create_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a YouTrack issue.

    config/input_data:
      api_key    — YouTrack permanent token (required)
      instance   — YouTrack cloud instance subdomain (required)
      project_id — project ID (required)
      summary    — issue summary (required)
      desc       — issue description (optional)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    instance = config.get("instance") or input_data.get("instance")
    if not api_key or not instance:
        raise ValueError("api_key and instance are required for youtrack.create_issue")

    project_id = config.get("project_id") or input_data.get("project_id")
    summary = config.get("summary") or input_data.get("summary")
    if not project_id or not summary:
        raise ValueError("project_id and summary are required for youtrack.create_issue")

    desc = config.get("desc") or input_data.get("desc", "")
    payload = {"project": {"id": project_id}, "summary": summary, "description": desc}

    async with httpx.AsyncClient(base_url=_base_url(instance), timeout=30) as client:
        r = await client.post("/issues", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        issue = r.json()

    log.info("youtrack.create_issue", issue_id=issue.get("id"), summary=summary)
    return {"issue": issue, "issue_id": issue.get("id")}


@register_node("youtrack.get_issue")
async def youtrack_get_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single YouTrack issue by ID.

    config/input_data:
      api_key  — YouTrack permanent token (required)
      instance — YouTrack cloud instance subdomain (required)
      issue_id — issue ID, e.g. "PROJ-123" (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    instance = config.get("instance") or input_data.get("instance")
    if not api_key or not instance:
        raise ValueError("api_key and instance are required for youtrack.get_issue")

    issue_id = config.get("issue_id") or input_data.get("issue_id")
    if not issue_id:
        raise ValueError("issue_id is required for youtrack.get_issue")

    async with httpx.AsyncClient(base_url=_base_url(instance), timeout=30) as client:
        r = await client.get(
            f"/issues/{issue_id}",
            params={"fields": "id,summary,description,state(name)"},
            headers=_headers(api_key),
        )
        r.raise_for_status()
        issue = r.json()

    log.info("youtrack.get_issue", issue_id=issue_id)
    return {"issue": issue}


@register_node("youtrack.list_projects")
async def youtrack_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List YouTrack projects.

    config:
      api_key  — YouTrack permanent token (required)
      instance — YouTrack cloud instance subdomain (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    instance = config.get("instance") or input_data.get("instance")
    if not api_key or not instance:
        raise ValueError("api_key and instance are required for youtrack.list_projects")

    async with httpx.AsyncClient(base_url=_base_url(instance), timeout=30) as client:
        r = await client.get(
            "/admin/projects",
            params={"fields": "id,name,shortName"},
            headers=_headers(api_key),
        )
        r.raise_for_status()
        projects = r.json()

    log.info("youtrack.list_projects", instance=instance, count=len(projects))
    return {"projects": projects, "count": len(projects)}
