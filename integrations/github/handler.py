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


# ─── Issues ──────────────────────────────────────────────────────────────────

@register_node("github.list_issues")
async def gh_list_issues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    # Support "owner/repo" shorthand in repo field
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    state = config.get("state", "open")
    labels = config.get("labels") or input_data.get("labels", "")
    milestone = config.get("milestone") or input_data.get("milestone")
    per_page = config.get("per_page", 30)
    page = config.get("page", 1)

    params = {"state": state, "per_page": per_page, "page": page}
    if labels:
        params["labels"] = labels if isinstance(labels, str) else ",".join(labels)
    if milestone:
        params["milestone"] = milestone

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/repos/{owner}/{repo}/issues", params=params)
        r.raise_for_status()
        issues = r.json()
    return {
        "issues": [
            {"number": i["number"], "title": i["title"], "state": i["state"],
             "url": i["html_url"], "author": i["user"]["login"]}
            for i in issues
        ],
        "count": len(issues),
    }


@register_node("github.update_issue")
async def gh_update_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    issue_number = config.get("issue_number") or input_data.get("issue_number")

    payload = {}
    for field in ("title", "body", "state", "labels", "assignees"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val

    async with await _gh(credential_id, db) as client:
        r = await client.patch(
            f"{GH_BASE}/repos/{owner}/{repo}/issues/{issue_number}", json=payload
        )
        r.raise_for_status()
        data = r.json()
    return {"issue_number": data["number"], "state": data["state"], "url": data["html_url"]}


# ─── Pull Requests ────────────────────────────────────────────────────────────

@register_node("github.get_pull_request")
async def gh_get_pull_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    pr_number = config.get("pr_number") or input_data.get("pr_number")

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/repos/{owner}/{repo}/pulls/{pr_number}")
        r.raise_for_status()
        data = r.json()
    return {
        "pr_number": data["number"], "title": data["title"], "state": data["state"],
        "url": data["html_url"], "merged": data.get("merged", False),
        "base": data["base"]["ref"], "head": data["head"]["ref"],
    }


@register_node("github.list_pull_requests")
async def gh_list_pull_requests(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    state = config.get("state", "open")
    base = config.get("base") or input_data.get("base")
    per_page = config.get("per_page", 30)

    params = {"state": state, "per_page": per_page}
    if base:
        params["base"] = base

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/repos/{owner}/{repo}/pulls", params=params)
        r.raise_for_status()
        prs = r.json()
    return {
        "pull_requests": [
            {"number": p["number"], "title": p["title"], "state": p["state"],
             "url": p["html_url"], "base": p["base"]["ref"], "head": p["head"]["ref"]}
            for p in prs
        ],
        "count": len(prs),
    }


@register_node("github.merge_pull_request")
async def gh_merge_pull_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    pr_number = config.get("pr_number") or input_data.get("pr_number")
    merge_method = config.get("merge_method", "merge")
    commit_title = config.get("commit_title") or input_data.get("commit_title")
    commit_message = config.get("commit_message") or input_data.get("commit_message")

    payload = {"merge_method": merge_method}
    if commit_title:
        payload["commit_title"] = commit_title
    if commit_message:
        payload["commit_message"] = commit_message

    async with await _gh(credential_id, db) as client:
        r = await client.put(
            f"{GH_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/merge", json=payload
        )
        r.raise_for_status()
        data = r.json()
    return {"merged": data.get("merged"), "sha": data.get("sha"), "message": data.get("message")}


# ─── Actions / Workflows ─────────────────────────────────────────────────────

@register_node("github.get_workflow_run")
async def gh_get_workflow_run(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    run_id = config.get("run_id") or input_data.get("run_id")

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/repos/{owner}/{repo}/actions/runs/{run_id}")
        r.raise_for_status()
        data = r.json()
    return {
        "run_id": data["id"], "name": data.get("name"), "status": data["status"],
        "conclusion": data.get("conclusion"), "url": data["html_url"],
        "workflow_id": data.get("workflow_id"),
    }


@register_node("github.list_workflow_runs")
async def gh_list_workflow_runs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    status = config.get("status") or input_data.get("status")
    per_page = config.get("per_page", 30)

    params = {"per_page": per_page}
    if status:
        params["status"] = status

    async with await _gh(credential_id, db) as client:
        if workflow_id:
            url = f"{GH_BASE}/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
        else:
            url = f"{GH_BASE}/repos/{owner}/{repo}/actions/runs"
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    runs = data.get("workflow_runs", [])
    return {
        "runs": [
            {"run_id": run["id"], "status": run["status"],
             "conclusion": run.get("conclusion"), "url": run["html_url"]}
            for run in runs
        ],
        "total_count": data.get("total_count", len(runs)),
    }


# ─── Releases ─────────────────────────────────────────────────────────────────

@register_node("github.list_releases")
async def gh_list_releases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    per_page = config.get("per_page", 30)

    async with await _gh(credential_id, db) as client:
        r = await client.get(
            f"{GH_BASE}/repos/{owner}/{repo}/releases", params={"per_page": per_page}
        )
        r.raise_for_status()
        releases = r.json()
    return {
        "releases": [
            {"id": rel["id"], "tag": rel["tag_name"], "name": rel["name"],
             "draft": rel["draft"], "prerelease": rel["prerelease"], "url": rel["html_url"]}
            for rel in releases
        ],
        "count": len(releases),
    }


# ─── Commits ─────────────────────────────────────────────────────────────────

@register_node("github.get_commit")
async def gh_get_commit(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    sha = config.get("sha") or input_data.get("sha")

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/repos/{owner}/{repo}/commits/{sha}")
        r.raise_for_status()
        data = r.json()
    commit = data["commit"]
    return {
        "sha": data["sha"], "url": data["html_url"],
        "message": commit["message"],
        "author": commit["author"]["name"],
        "date": commit["author"]["date"],
        "files_changed": len(data.get("files", [])),
    }


@register_node("github.list_commits")
async def gh_list_commits(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    sha = config.get("sha") or input_data.get("sha")
    since = config.get("since") or input_data.get("since")
    until = config.get("until") or input_data.get("until")
    per_page = config.get("per_page", 30)

    params = {"per_page": per_page}
    if sha:
        params["sha"] = sha
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    async with await _gh(credential_id, db) as client:
        r = await client.get(f"{GH_BASE}/repos/{owner}/{repo}/commits", params=params)
        r.raise_for_status()
        commits = r.json()
    return {
        "commits": [
            {"sha": c["sha"], "message": c["commit"]["message"],
             "author": c["commit"]["author"]["name"], "url": c["html_url"]}
            for c in commits
        ],
        "count": len(commits),
    }


# ─── File Contents (alias with owner/repo split support) ─────────────────────

@register_node("github.get_file_contents")
async def gh_get_file_contents(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Alias for get_file with explicit owner/repo params and base64 decoding."""
    import base64
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    path = config.get("path") or input_data.get("path")
    ref = config.get("ref") or input_data.get("ref", "main")

    async with await _gh(credential_id, db) as client:
        r = await client.get(
            f"{GH_BASE}/repos/{owner}/{repo}/contents/{path}", params={"ref": ref}
        )
        r.raise_for_status()
        data = r.json()
    content = base64.b64decode(data["content"]).decode(errors="replace") if data.get("content") else ""
    return {"path": data["path"], "content": content, "sha": data["sha"], "size": data.get("size")}


# ─── Webhooks ─────────────────────────────────────────────────────────────────

@register_node("github.create_webhook")
async def gh_create_webhook(config: dict, input_data: dict, credential_id: str, db) -> dict:
    owner = config.get("owner") or input_data.get("owner")
    repo = config.get("repo") or input_data.get("repo")
    if not owner and repo and "/" in repo:
        owner, repo = repo.split("/", 1)
    url = config.get("url") or input_data.get("url")
    events = config.get("events") or input_data.get("events", ["push"])
    secret = config.get("secret") or input_data.get("secret")

    if isinstance(events, str):
        events = [e.strip() for e in events.split(",")]

    config_payload = {"url": url, "content_type": "json"}
    if secret:
        config_payload["secret"] = secret

    async with await _gh(credential_id, db) as client:
        r = await client.post(
            f"{GH_BASE}/repos/{owner}/{repo}/hooks",
            json={"name": "web", "active": True, "events": events, "config": config_payload},
        )
        r.raise_for_status()
        data = r.json()
    return {"hook_id": data["id"], "url": url, "events": events, "active": data.get("active")}


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
