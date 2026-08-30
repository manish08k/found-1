"""GitLab integration — projects, issues, merge requests, pipelines, files, tags.

Nodes: gitlab.list_projects, gitlab.get_project, gitlab.list_issues,
       gitlab.create_issue, gitlab.update_issue, gitlab.add_comment,
       gitlab.list_merge_requests, gitlab.create_merge_request,
       gitlab.merge_merge_request, gitlab.list_pipelines, gitlab.get_pipeline,
       gitlab.trigger_pipeline, gitlab.retry_pipeline, gitlab.get_file,
       gitlab.list_commits, gitlab.create_tag

Credential fields: personal_access_token, base_url (default: https://gitlab.com)
"""
import urllib.parse
import httpx
import structlog

from core.execution_engine import register_node
from credentials.encryption import decrypt_credential

log = structlog.get_logger(__name__)


async def _gl(credential_id: str, db) -> tuple[str, httpx.AsyncClient]:
    """Return (api_base_url, async_client) authenticated with the credential."""
    from storage.database import AsyncSessionLocal
    from storage.models import Credential
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Credential).where(Credential.id == credential_id))
        cred = result.scalar_one_or_none()
        if not cred:
            raise ValueError(f"Credential {credential_id} not found")
        from core.config import settings
        data = decrypt_credential(cred.encrypted_data, settings.ENCRYPTION_KEY)

    token = data.get("personal_access_token")
    if not token:
        raise ValueError("GitLab credential missing 'personal_access_token'")

    base_url = data.get("base_url", "https://gitlab.com").rstrip("/")
    api_base = f"{base_url}/api/v4"

    client = httpx.AsyncClient(
        headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
        timeout=30.0,
    )
    return api_base, client


# ─── Projects ─────────────────────────────────────────────────────────────────

@register_node("gitlab.list_projects")
async def gl_list_projects(config: dict, input_data: dict, credential_id: str, db) -> dict:
    membership = config.get("membership", True)
    owned = config.get("owned", False)
    search = config.get("search") or input_data.get("search")
    per_page = config.get("per_page", 20)
    page = config.get("page", 1)

    params = {"membership": str(membership).lower(), "owned": str(owned).lower(),
              "per_page": per_page, "page": page}
    if search:
        params["search"] = search

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(f"{api_base}/projects", params=params)
        r.raise_for_status()
        projects = r.json()
    return {
        "projects": [
            {"id": p["id"], "name": p["name"], "path": p["path_with_namespace"],
             "url": p.get("web_url"), "visibility": p.get("visibility")}
            for p in projects
        ],
        "count": len(projects),
    }


@register_node("gitlab.get_project")
async def gl_get_project(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(f"{api_base}/projects/{project_id}")
        r.raise_for_status()
        data = r.json()
    return {
        "id": data["id"], "name": data["name"], "path": data["path_with_namespace"],
        "url": data.get("web_url"), "visibility": data.get("visibility"),
        "default_branch": data.get("default_branch"),
        "description": data.get("description"),
    }


# ─── Issues ───────────────────────────────────────────────────────────────────

@register_node("gitlab.list_issues")
async def gl_list_issues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    state = config.get("state", "opened")
    labels = config.get("labels") or input_data.get("labels")
    per_page = config.get("per_page", 20)
    page = config.get("page", 1)

    params = {"state": state, "per_page": per_page, "page": page}
    if labels:
        params["labels"] = labels if isinstance(labels, str) else ",".join(labels)

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(f"{api_base}/projects/{project_id}/issues", params=params)
        r.raise_for_status()
        issues = r.json()
    return {
        "issues": [
            {"iid": i["iid"], "title": i["title"], "state": i["state"],
             "url": i.get("web_url"), "author": i["author"]["username"]}
            for i in issues
        ],
        "count": len(issues),
    }


@register_node("gitlab.create_issue")
async def gl_create_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    title = config.get("title") or input_data.get("title")
    description = config.get("description") or input_data.get("description", "")
    labels = config.get("labels") or input_data.get("labels")
    assignee_ids = config.get("assignee_ids") or input_data.get("assignee_ids")
    milestone_id = config.get("milestone_id") or input_data.get("milestone_id")

    payload = {"title": title, "description": description}
    if labels:
        payload["labels"] = labels if isinstance(labels, str) else ",".join(labels)
    if assignee_ids:
        payload["assignee_ids"] = assignee_ids
    if milestone_id:
        payload["milestone_id"] = milestone_id

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.post(f"{api_base}/projects/{project_id}/issues", json=payload)
        r.raise_for_status()
        data = r.json()
    return {"iid": data["iid"], "id": data["id"], "title": data["title"], "url": data.get("web_url")}


@register_node("gitlab.update_issue")
async def gl_update_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    issue_iid = config.get("issue_iid") or input_data.get("issue_iid")

    payload = {}
    for field in ("title", "description", "state_event", "labels"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val
    if "labels" in payload and isinstance(payload["labels"], list):
        payload["labels"] = ",".join(payload["labels"])

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.put(
            f"{api_base}/projects/{project_id}/issues/{issue_iid}", json=payload
        )
        r.raise_for_status()
        data = r.json()
    return {"iid": data["iid"], "state": data["state"], "url": data.get("web_url")}


@register_node("gitlab.add_comment")
async def gl_add_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    issue_iid = config.get("issue_iid") or input_data.get("issue_iid")
    body = config.get("body") or input_data.get("body", "")

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.post(
            f"{api_base}/projects/{project_id}/issues/{issue_iid}/notes",
            json={"body": body},
        )
        r.raise_for_status()
        data = r.json()
    return {"note_id": data["id"], "body": data["body"]}


# ─── Merge Requests ───────────────────────────────────────────────────────────

@register_node("gitlab.list_merge_requests")
async def gl_list_merge_requests(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    state = config.get("state", "opened")
    per_page = config.get("per_page", 20)

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(
            f"{api_base}/projects/{project_id}/merge_requests",
            params={"state": state, "per_page": per_page},
        )
        r.raise_for_status()
        mrs = r.json()
    return {
        "merge_requests": [
            {"iid": m["iid"], "title": m["title"], "state": m["state"],
             "url": m.get("web_url"), "source_branch": m["source_branch"],
             "target_branch": m["target_branch"]}
            for m in mrs
        ],
        "count": len(mrs),
    }


@register_node("gitlab.create_merge_request")
async def gl_create_merge_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    source_branch = config.get("source_branch") or input_data.get("source_branch")
    target_branch = config.get("target_branch") or input_data.get("target_branch")
    title = config.get("title") or input_data.get("title")
    description = config.get("description") or input_data.get("description", "")
    assignee_id = config.get("assignee_id") or input_data.get("assignee_id")

    payload = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "description": description,
    }
    if assignee_id:
        payload["assignee_id"] = assignee_id

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.post(
            f"{api_base}/projects/{project_id}/merge_requests", json=payload
        )
        r.raise_for_status()
        data = r.json()
    return {"iid": data["iid"], "title": data["title"], "url": data.get("web_url"), "state": data["state"]}


@register_node("gitlab.merge_merge_request")
async def gl_merge_merge_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    mr_iid = config.get("mr_iid") or input_data.get("mr_iid")
    should_remove_source_branch = config.get("should_remove_source_branch", False)

    payload = {"should_remove_source_branch": should_remove_source_branch}

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.put(
            f"{api_base}/projects/{project_id}/merge_requests/{mr_iid}/merge", json=payload
        )
        r.raise_for_status()
        data = r.json()
    return {"iid": data["iid"], "state": data["state"], "merged_at": data.get("merged_at")}


# ─── Pipelines ────────────────────────────────────────────────────────────────

@register_node("gitlab.list_pipelines")
async def gl_list_pipelines(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    status = config.get("status") or input_data.get("status")
    per_page = config.get("per_page", 20)

    params = {"per_page": per_page}
    if status:
        params["status"] = status

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(f"{api_base}/projects/{project_id}/pipelines", params=params)
        r.raise_for_status()
        pipelines = r.json()
    return {
        "pipelines": [
            {"id": p["id"], "status": p["status"], "ref": p["ref"],
             "sha": p["sha"], "url": p.get("web_url")}
            for p in pipelines
        ],
        "count": len(pipelines),
    }


@register_node("gitlab.get_pipeline")
async def gl_get_pipeline(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(f"{api_base}/projects/{project_id}/pipelines/{pipeline_id}")
        r.raise_for_status()
        data = r.json()
    return {
        "id": data["id"], "status": data["status"], "ref": data["ref"],
        "sha": data["sha"], "url": data.get("web_url"),
        "duration": data.get("duration"),
        "created_at": data.get("created_at"), "finished_at": data.get("finished_at"),
    }


@register_node("gitlab.trigger_pipeline")
async def gl_trigger_pipeline(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    ref = config.get("ref") or input_data.get("ref", "main")
    variables = config.get("variables") or input_data.get("variables", [])

    payload = {"ref": ref, "variables": variables}

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.post(f"{api_base}/projects/{project_id}/pipeline", json=payload)
        r.raise_for_status()
        data = r.json()
    return {"id": data["id"], "status": data["status"], "ref": data["ref"], "url": data.get("web_url")}


@register_node("gitlab.retry_pipeline")
async def gl_retry_pipeline(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.post(
            f"{api_base}/projects/{project_id}/pipelines/{pipeline_id}/retry"
        )
        r.raise_for_status()
        data = r.json()
    return {"id": data["id"], "status": data["status"]}


# ─── Repository ───────────────────────────────────────────────────────────────

@register_node("gitlab.get_file")
async def gl_get_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    import base64
    project_id = config.get("project_id") or input_data.get("project_id")
    file_path = config.get("file_path") or input_data.get("file_path")
    ref = config.get("ref") or input_data.get("ref", "main")

    encoded_path = urllib.parse.quote(file_path, safe="")

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(
            f"{api_base}/projects/{project_id}/repository/files/{encoded_path}",
            params={"ref": ref},
        )
        r.raise_for_status()
        data = r.json()
    content_raw = data.get("content", "")
    content = base64.b64decode(content_raw).decode(errors="replace") if content_raw else ""
    return {
        "file_path": data["file_path"], "content": content,
        "sha": data.get("content_sha256"), "ref": data.get("ref"),
        "size": data.get("size"),
    }


@register_node("gitlab.list_commits")
async def gl_list_commits(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    ref_name = config.get("ref_name") or input_data.get("ref_name")
    since = config.get("since") or input_data.get("since")
    until = config.get("until") or input_data.get("until")
    per_page = config.get("per_page", 20)

    params = {"per_page": per_page}
    if ref_name:
        params["ref_name"] = ref_name
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.get(
            f"{api_base}/projects/{project_id}/repository/commits", params=params
        )
        r.raise_for_status()
        commits = r.json()
    return {
        "commits": [
            {"id": c["id"], "short_id": c["short_id"], "title": c["title"],
             "author_name": c["author_name"], "created_at": c["created_at"],
             "url": c.get("web_url")}
            for c in commits
        ],
        "count": len(commits),
    }


@register_node("gitlab.create_tag")
async def gl_create_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    project_id = config.get("project_id") or input_data.get("project_id")
    tag_name = config.get("tag_name") or input_data.get("tag_name")
    ref = config.get("ref") or input_data.get("ref", "main")
    message = config.get("message") or input_data.get("message")

    payload = {"tag_name": tag_name, "ref": ref}
    if message:
        payload["message"] = message

    api_base, client = await _gl(credential_id, db)
    async with client:
        r = await client.post(
            f"{api_base}/projects/{project_id}/repository/tags", json=payload
        )
        r.raise_for_status()
        data = r.json()
    return {
        "name": data["name"], "ref": ref,
        "commit": data.get("commit", {}).get("id"),
        "message": data.get("message"),
    }
