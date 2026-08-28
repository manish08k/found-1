"""GitHub integration — repos, issues, PRs, files, releases + webhook triggers."""
import structlog
import httpx

from core.execution_engine import register_node
from triggers.engine import register_poller
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)

GH_BASE = "https://api.github.com"


async def _gh(credential_id: str, db) -> httpx.AsyncClient:
    token = await get_access_token(credential_id, db)
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )


@register_node("github.create_issue")
async def gh_create_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    repo = config.get("repo") or input_data.get("repo")  # "owner/repo"
    title = config.get("title") or input_data.get("title")
    body = config.get("body") or input_data.get("body", "")
    labels = config.get("labels") or input_data.get("labels", [])
    assignees = config.get("assignees") or input_data.get("assignees", [])

    async with await _gh(credential_id, db) as client:
        r = await client.post(f"{GH_BASE}/repos/{repo}/issues", json={
            "title": title, "body": body, "labels": labels, "assignees": assignees,
        })
        r.raise_for_status()
        data = r.json()
    return {"issue_number": data["number"], "url": data["html_url"], "id": data["id"]}


@register_node("github.close_issue")
async def gh_close_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    repo = config.get("repo") or input_data.get("repo")
    issue_number = config.get("issue_number") or input_data.get("issue_number")

    async with await _gh(credential_id, db) as client:
        r = await client.patch(f"{GH_BASE}/repos/{repo}/issues/{issue_number}",
                               json={"state": "closed"})
        r.raise_for_status()
    return {"ok": True, "issue_number": issue_number}


@register_node("github.add_comment")
async def gh_add_comment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    repo = config.get("repo") or input_data.get("repo")
    issue_number = config.get("issue_number") or input_data.get("issue_number")
    body = config.get("body") or input_data.get("body", "")

    async with await _gh(credential_id, db) as client:
        r = await client.post(
            f"{GH_BASE}/repos/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        r.raise_for_status()
        data = r.json()
    return {"comment_id": data["id"], "url": data["html_url"]}


@register_node("github.create_pr")
async def gh_create_pr(config: dict, input_data: dict, credential_id: str, db) -> dict:
    repo = config.get("repo") or input_data.get("repo")
    title = config.get("title") or input_data.get("title")
    head = config.get("head") or input_data.get("head")
    base = config.get("base", "main")
    body = config.get("body", "")
    draft = config.get("draft", False)

    async with await _gh(credential_id, db) as client:
        r = await client.post(f"{GH_BASE}/repos/{repo}/pulls", json={
            "title": title, "head": head, "base": base, "body": body, "draft": draft,
        })
        r.raise_for_status()
        data = r.json()
    return {"pr_number": data["number"], "url": data["html_url"]}


@register_node("github.merge_pr")
async def gh_merge_pr(config: dict, input_data: dict, credential_id: str, db) -> dict:
    repo = config.get("repo") or input_data.get("repo")
    pr_number = config.get("pr_number") or input_data.get("pr_number")
    merge_method = config.get("merge_method", "squash")

    async with await _gh(credential_id, db) as client:
        r = await client.put(
            f"{GH_BASE}/repos/{repo}/pulls/{pr_number}/merge",
            json={"merge_method": merge_method},
        )
        r.raise_for_status()
        data = r.json()
    return {"merged": data.get("merged"), "sha": data.get("sha")}


@register_node("github.get_file")
async def gh_get_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    import base64
    repo = config.get("repo") or input_data.get("repo")
    path = config.get("path") or input_data.get("path")
    ref = config.get("ref", "main")

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/repos/{repo}/contents/{path}",
                             params={"ref": ref})
        r.raise_for_status()
        data = r.json()

    content = base64.b64decode(data["content"]).decode(errors="replace") if data.get("content") else ""
    return {"path": data["path"], "content": content, "sha": data["sha"]}


@register_node("github.create_or_update_file")
async def gh_create_or_update_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    import base64
    repo = config.get("repo") or input_data.get("repo")
    path = config.get("path") or input_data.get("path")
    message = config.get("message") or input_data.get("message", "Update file")
    content = config.get("content") or input_data.get("content", "")
    branch = config.get("branch", "main")
    sha = config.get("sha") or input_data.get("sha")  # required for updates

    encoded = base64.b64encode(content.encode()).decode()
    payload = {"message": message, "content": encoded, "branch": branch}
    if sha:
        payload["sha"] = sha

    async with await _gh(credential_id, db) as client:
        r = await client.put(f"{GH_BASE}/repos/{repo}/contents/{path}", json=payload)
        r.raise_for_status()
        data = r.json()
    return {"path": path, "sha": data["content"]["sha"], "url": data["content"]["html_url"]}


@register_node("github.create_release")
async def gh_create_release(config: dict, input_data: dict, credential_id: str, db) -> dict:
    repo = config.get("repo") or input_data.get("repo")
    tag = config.get("tag_name") or input_data.get("tag_name")
    name = config.get("name") or input_data.get("name", tag)
    body = config.get("body", "")
    draft = config.get("draft", False)
    prerelease = config.get("prerelease", False)

    async with await _gh(credential_id, db) as client:
        r = await client.post(f"{GH_BASE}/repos/{repo}/releases", json={
            "tag_name": tag, "name": name, "body": body,
            "draft": draft, "prerelease": prerelease,
        })
        r.raise_for_status()
        data = r.json()
    return {"release_id": data["id"], "url": data["html_url"], "tag": tag}


@register_node("github.list_repos")
async def gh_list_repos(config: dict, input_data: dict, credential_id: str, db) -> dict:
    per_page = config.get("per_page", 30)
    visibility = config.get("visibility", "all")

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/user/repos",
                             params={"per_page": per_page, "visibility": visibility})
        r.raise_for_status()
        repos = r.json()
    return {"repos": [{"id": r["id"], "name": r["full_name"], "url": r["html_url"]} for r in repos]}


@register_node("github.trigger_workflow")
async def gh_trigger_workflow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    repo = config.get("repo") or input_data.get("repo")
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    ref = config.get("ref", "main")
    inputs = config.get("inputs") or input_data.get("inputs", {})

    async with await _gh(credential_id, db) as client:
        r = await client.post(
            f"{GH_BASE}/repos/{repo}/actions/workflows/{workflow_id}/dispatches",
            json={"ref": ref, "inputs": inputs},
        )
        r.raise_for_status()
    return {"ok": True}


# ─── Polling: new issues ──────────────────────────────────────────────────────

_gh_seen_issues: dict[str, set] = {}


@register_poller("github", "new_issue")
async def poll_github_issues(config: dict, credential_id: str, db) -> list[dict]:
    repo = config.get("repo")
    key = f"{credential_id}:{repo}"
    if key not in _gh_seen_issues:
        _gh_seen_issues[key] = set()

    try:
        async with await _gh(credential_id, db) as client:
            r = await client.get(f"{GH_BASE}/repos/{repo}/issues",
                                 params={"state": "open", "per_page": 20, "sort": "created"})
            r.raise_for_status()
            issues = r.json()

        new_items = []
        for issue in issues:
            if str(issue["number"]) not in _gh_seen_issues[key]:
                new_items.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "url": issue["html_url"],
                    "author": issue["user"]["login"],
                })
                _gh_seen_issues[key].add(str(issue["number"]))
        return new_items
    except Exception as e:
        log.error("github_poll_error", error=str(e))
        return []
