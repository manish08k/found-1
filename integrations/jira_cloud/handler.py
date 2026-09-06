"""Jira Cloud (Activepieces variant) — handler for jira_cloud integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://your-domain.atlassian.net/rest/api/3"


@register_node("jira_cloud.list_projects")
async def jira_cloud_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    email = merged.get("email") or ""
    api_token = merged.get("api_token") or merged.get("api_key") or ""
    import base64
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/project", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("jira_cloud.list_projects")
    return {"data": data}

@register_node("jira_cloud.create_issue")
async def jira_cloud_create_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an issue.

    config/input_data:
      api_key — API key or token (required)
      fields — (required)
    """
    merged = {**config, **input_data}
    email = merged.get("email") or ""
    api_token = merged.get("api_token") or merged.get("api_key") or ""
    import base64
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    fields = merged.get("fields") or ""
    if not fields:
        raise ValueError("fields required for jira_cloud.create_issue")
    payload = {"fields": fields}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/issue", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("jira_cloud.create_issue")
    return {"data": data}

@register_node("jira_cloud.get_issue")
async def jira_cloud_get_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get issue details.

    config/input_data:
      api_key — API key or token (required)
      issue_key — (required)
    """
    merged = {**config, **input_data}
    email = merged.get("email") or ""
    api_token = merged.get("api_token") or merged.get("api_key") or ""
    import base64
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    issue_key = merged.get("issue_key") or ""
    if not issue_key:
        raise ValueError("issue_key required for jira_cloud.get_issue")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/issue/{issue_key}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("jira_cloud.get_issue")
    return {"data": data}

@register_node("jira_cloud.search_issues")
async def jira_cloud_search_issues(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search issues with JQL.

    config/input_data:
      api_key — API key or token (required)
      jql — (required)
    """
    merged = {**config, **input_data}
    email = merged.get("email") or ""
    api_token = merged.get("api_token") or merged.get("api_key") or ""
    import base64
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    jql = merged.get("jql") or ""
    if not jql:
        raise ValueError("jql required for jira_cloud.search_issues")
    payload = {"jql": jql}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/search", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("jira_cloud.search_issues")
    return {"data": data}
