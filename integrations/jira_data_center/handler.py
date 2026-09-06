"""Jira Data Center / Server (Activepieces variant) — handler for jira_data_center integration."""
import base64

import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL_TEMPLATE = "https://{server}/rest/api/2"


def _build_base_url(merged: dict) -> str:
    server = merged.get("server") or merged.get("host") or ""
    if not server:
        raise ValueError("server (hostname) is required for jira_data_center operations")
    return BASE_URL_TEMPLATE.format(server=server)


def _build_headers(merged: dict) -> dict:
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}


@register_node("jira_data_center.list_projects")
async def jira_data_center_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List projects.

    config/input_data:
      server / host — Jira server hostname (required)
      username / api_key — (required)
      password / api_token — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/project", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("jira_data_center.list_projects")
    return {"data": data}

@register_node("jira_data_center.create_issue")
async def jira_data_center_create_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an issue.

    config/input_data:
      server / host — Jira server hostname (required)
      username / api_key — (required)
      password / api_token — (required)
      fields — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    fields = merged.get("fields") or ""
    if not fields:
        raise ValueError("fields required for jira_data_center.create_issue")
    payload = {"fields": fields}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/issue", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("jira_data_center.create_issue")
    return {"data": data}

@register_node("jira_data_center.get_issue")
async def jira_data_center_get_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get issue details.

    config/input_data:
      server / host — Jira server hostname (required)
      username / api_key — (required)
      password / api_token — (required)
      issue_key — (required)
    """
    merged = {**config, **input_data}
    base_url = _build_base_url(merged)
    headers = _build_headers(merged)
    issue_key = merged.get("issue_key") or ""
    if not issue_key:
        raise ValueError("issue_key required for jira_data_center.get_issue")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/issue/{issue_key}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("jira_data_center.get_issue")
    return {"data": data}
