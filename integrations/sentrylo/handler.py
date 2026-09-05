"""
Sentry error tracking integration.

Credential fields:
  - auth_token: Sentry API auth token
  - org_slug   : Organization slug in Sentry

Auth: Authorization: Bearer {auth_token}
Base URL: https://sentry.io/api/0/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://sentry.io/api/0/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    auth_token = creds.get("auth_token")
    if not auth_token:
        raise ValueError("Sentry credential missing 'auth_token'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def _get_org_slug(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    org_slug = creds.get("org_slug")
    if not org_slug:
        raise ValueError("Sentry credential missing 'org_slug'")
    return org_slug


def _raise_for_status(r: httpx.Response) -> dict:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Sentry API error {r.status_code}: {detail}")
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


@register_node("sentrylo.list_projects")
async def sentry_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all projects in the organization."""
    org_slug = await _get_org_slug(credential_id, db)
    cursor = config.get("cursor") or input_data.get("cursor")

    params: dict = {}
    if cursor:
        params["cursor"] = cursor

    log.info("sentrylo.list_projects", org_slug=org_slug)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"organizations/{org_slug}/projects/", params=params)
    data = _raise_for_status(r)
    if isinstance(data, list):
        return {"projects": data, "count": len(data)}
    return {"projects": data.get("projects", data), "count": len(data) if isinstance(data, list) else 0}


@register_node("sentrylo.list_issues")
async def sentry_list_issues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List issues (errors) for a project."""
    org_slug = await _get_org_slug(credential_id, db)
    project_slug = config.get("project_slug") or input_data.get("project_slug")
    query = config.get("query") or input_data.get("query", "is:unresolved")
    limit = min(int(config.get("limit") or input_data.get("limit", 25)), 100)

    if not project_slug:
        raise ValueError("sentrylo.list_issues requires 'project_slug'")

    params = {"query": query, "limit": limit}

    log.info("sentrylo.list_issues", org_slug=org_slug, project_slug=project_slug, query=query)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"projects/{org_slug}/{project_slug}/issues/", params=params)
    issues = _raise_for_status(r)
    if not isinstance(issues, list):
        issues = []
    return {"issues": issues, "count": len(issues)}


@register_node("sentrylo.resolve_issue")
async def sentry_resolve_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Mark an issue as resolved."""
    issue_id = config.get("issue_id") or input_data.get("issue_id")
    if not issue_id:
        raise ValueError("sentrylo.resolve_issue requires 'issue_id'")

    log.info("sentrylo.resolve_issue", issue_id=issue_id)
    async with await _client(credential_id, db) as client:
        r = await client.put(f"issues/{issue_id}/", json={"status": "resolved"})
    data = _raise_for_status(r)
    return {"issue": data, "issue_id": issue_id, "status": "resolved"}


@register_node("sentrylo.create_release")
async def sentry_create_release(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new release in Sentry."""
    org_slug = await _get_org_slug(credential_id, db)
    version = config.get("version") or input_data.get("version")
    projects = config.get("projects") or input_data.get("projects", [])
    ref = config.get("ref") or input_data.get("ref", "")
    url = config.get("url") or input_data.get("url", "")

    if not version:
        raise ValueError("sentrylo.create_release requires 'version'")
    if isinstance(projects, str):
        projects = [p.strip() for p in projects.split(",") if p.strip()]

    payload: dict = {"version": version, "projects": projects}
    if ref:
        payload["refs"] = [{"repository": ref, "commit": version}]
    if url:
        payload["url"] = url

    log.info("sentrylo.create_release", org_slug=org_slug, version=version)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"organizations/{org_slug}/releases/", json=payload)
    data = _raise_for_status(r)
    return {"release": data, "version": version}
