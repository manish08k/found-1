"""Taiga project management integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


async def _get_token(client: httpx.AsyncClient, host: str, username: str, password: str) -> str:
    """Authenticate with Taiga and return auth token."""
    r = await client.post(
        f"{host}/api/v1/auth",
        json={"type": "normal", "username": username, "password": password},
    )
    r.raise_for_status()
    return r.json()["auth_token"]


def _build_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("taiga.list_projects")
async def list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Taiga projects accessible to the authenticated user.

    config:
      host     — Taiga host URL (e.g. https://api.taiga.io)
      username — Taiga username
      password — Taiga password
    """
    merged = {**config, **input_data}
    host = (merged.get("host") or "").rstrip("/")
    username = merged.get("username") or ""
    password = merged.get("password") or ""

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client, host, username, password)
        r = await client.get(f"{host}/api/v1/projects", headers=_build_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("taiga.list_projects", count=len(data))
    return {"projects": data, "count": len(data)}


@register_node("taiga.get_project")
async def get_project(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Taiga project by ID.

    config/input_data:
      host       — Taiga host URL
      username   — Taiga username
      password   — Taiga password
      project_id — project ID (required)
    """
    merged = {**config, **input_data}
    host = (merged.get("host") or "").rstrip("/")
    username = merged.get("username") or ""
    password = merged.get("password") or ""
    project_id = merged.get("project_id") or ""

    if not project_id:
        raise ValueError("project_id is required for taiga.get_project")

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client, host, username, password)
        r = await client.get(f"{host}/api/v1/projects/{project_id}", headers=_build_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("taiga.get_project", project_id=project_id)
    return {"project": data}


@register_node("taiga.list_user_stories")
async def list_user_stories(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List user stories for a project.

    config/input_data:
      host       — Taiga host URL
      username   — Taiga username
      password   — Taiga password
      project_id — project ID (required)
    """
    merged = {**config, **input_data}
    host = (merged.get("host") or "").rstrip("/")
    username = merged.get("username") or ""
    password = merged.get("password") or ""
    project_id = merged.get("project_id") or ""

    if not project_id:
        raise ValueError("project_id is required for taiga.list_user_stories")

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client, host, username, password)
        r = await client.get(
            f"{host}/api/v1/userstories",
            headers=_build_headers(token),
            params={"project": project_id},
        )
        r.raise_for_status()
        data = r.json()

    log.info("taiga.list_user_stories", project_id=project_id, count=len(data))
    return {"user_stories": data, "count": len(data)}


@register_node("taiga.create_user_story")
async def create_user_story(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a user story in a Taiga project.

    config/input_data:
      host        — Taiga host URL
      username    — Taiga username
      password    — Taiga password
      project_id  — project ID (required)
      subject     — user story subject/title (required)
      description — optional description
    """
    merged = {**config, **input_data}
    host = (merged.get("host") or "").rstrip("/")
    username = merged.get("username") or ""
    password = merged.get("password") or ""
    project_id = merged.get("project_id") or ""
    subject = merged.get("subject") or ""
    description = merged.get("description") or ""

    if not project_id:
        raise ValueError("project_id is required for taiga.create_user_story")
    if not subject:
        raise ValueError("subject is required for taiga.create_user_story")

    payload: dict = {"project": project_id, "subject": subject}
    if description:
        payload["description"] = description

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client, host, username, password)
        r = await client.post(f"{host}/api/v1/userstories", json=payload, headers=_build_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("taiga.create_user_story", project_id=project_id, subject=subject)
    return {"user_story": data, "id": data.get("id")}


@register_node("taiga.list_issues")
async def list_issues(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List issues for a Taiga project.

    config/input_data:
      host       — Taiga host URL
      username   — Taiga username
      password   — Taiga password
      project_id — project ID (required)
    """
    merged = {**config, **input_data}
    host = (merged.get("host") or "").rstrip("/")
    username = merged.get("username") or ""
    password = merged.get("password") or ""
    project_id = merged.get("project_id") or ""

    if not project_id:
        raise ValueError("project_id is required for taiga.list_issues")

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client, host, username, password)
        r = await client.get(
            f"{host}/api/v1/issues",
            headers=_build_headers(token),
            params={"project": project_id},
        )
        r.raise_for_status()
        data = r.json()

    log.info("taiga.list_issues", project_id=project_id, count=len(data))
    return {"issues": data, "count": len(data)}


@register_node("taiga.create_issue")
async def create_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an issue in a Taiga project.

    config/input_data:
      host        — Taiga host URL
      username    — Taiga username
      password    — Taiga password
      project_id  — project ID (required)
      subject     — issue subject/title (required)
      priority    — priority (required)
      severity    — severity (required)
      type        — issue type (required)
      description — optional description
    """
    merged = {**config, **input_data}
    host = (merged.get("host") or "").rstrip("/")
    username = merged.get("username") or ""
    password = merged.get("password") or ""
    project_id = merged.get("project_id") or ""
    subject = merged.get("subject") or ""
    priority = merged.get("priority") or ""
    severity = merged.get("severity") or ""
    issue_type = merged.get("type") or ""
    description = merged.get("description") or ""

    if not project_id:
        raise ValueError("project_id is required for taiga.create_issue")
    if not subject:
        raise ValueError("subject is required for taiga.create_issue")

    payload: dict = {
        "project": project_id,
        "subject": subject,
        "priority": priority,
        "severity": severity,
        "type": issue_type,
    }
    if description:
        payload["description"] = description

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client, host, username, password)
        r = await client.post(f"{host}/api/v1/issues", json=payload, headers=_build_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("taiga.create_issue", project_id=project_id, subject=subject)
    return {"issue": data, "id": data.get("id")}


@register_node("taiga.get_me")
async def get_me(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the currently authenticated Taiga user.

    config:
      host     — Taiga host URL
      username — Taiga username
      password — Taiga password
    """
    merged = {**config, **input_data}
    host = (merged.get("host") or "").rstrip("/")
    username = merged.get("username") or ""
    password = merged.get("password") or ""

    async with httpx.AsyncClient(timeout=30) as client:
        token = await _get_token(client, host, username, password)
        r = await client.get(f"{host}/api/v1/users/me", headers=_build_headers(token))
        r.raise_for_status()
        data = r.json()

    log.info("taiga.get_me", username=data.get("username"))
    return {"user": data}
