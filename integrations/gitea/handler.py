"""Gitea integration — repositories, issues, branches, and releases."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _gitea_headers(access_token: str) -> dict:
    return {"Authorization": f"token {access_token}", "Content-Type": "application/json"}


def _api_base(base_url: str) -> str:
    return base_url.rstrip("/") + "/api/v1"


@register_node("gitea.list_repos")
async def gitea_list_repos(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List repositories accessible to the authenticated user.

    config:
      base_url     — Gitea instance URL e.g. https://gitea.example.com (required)
      access_token — Gitea access token (required)
      limit        — maximum number of repos to return (optional, default 50)
      page         — page number (optional, default 1)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    access_token = merged.get("access_token", "")
    if not base_url:
        raise ValueError("base_url is required for gitea.list_repos")

    params = {"limit": merged.get("limit", 50), "page": merged.get("page", 1)}

    async with httpx.AsyncClient(base_url=_api_base(base_url), timeout=30) as client:
        r = await client.get("/repos/search", headers=_gitea_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    repos = data.get("data", [])
    log.info("gitea.list_repos", count=len(repos))
    return {"repos": repos, "count": len(repos)}


@register_node("gitea.get_repo")
async def gitea_get_repo(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Gitea repository.

    config:
      base_url     — Gitea instance URL (required)
      access_token — Gitea access token (required)
      owner        — repository owner (required)
      repo         — repository name (required)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    access_token = merged.get("access_token", "")
    owner = merged.get("owner")
    repo = merged.get("repo")

    if not base_url or not owner or not repo:
        raise ValueError("base_url, owner, and repo are required for gitea.get_repo")

    async with httpx.AsyncClient(base_url=_api_base(base_url), timeout=30) as client:
        r = await client.get(f"/repos/{owner}/{repo}", headers=_gitea_headers(access_token))
        r.raise_for_status()
        repository = r.json()

    log.info("gitea.get_repo", owner=owner, repo=repo)
    return {"repo": repository}


@register_node("gitea.create_repo")
async def gitea_create_repo(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Gitea repository for the authenticated user.

    config:
      base_url     — Gitea instance URL (required)
      access_token — Gitea access token (required)
      name         — repository name (required)
      description  — repository description (optional)
      private      — whether the repo is private, default False
      auto_init    — initialize with README, default False
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    access_token = merged.get("access_token", "")
    name = merged.get("name")

    if not base_url or not name:
        raise ValueError("base_url and name are required for gitea.create_repo")

    payload: dict = {
        "name": name,
        "description": merged.get("description", ""),
        "private": merged.get("private", False),
        "auto_init": merged.get("auto_init", False),
    }

    async with httpx.AsyncClient(base_url=_api_base(base_url), timeout=30) as client:
        r = await client.post(
            "/user/repos", headers=_gitea_headers(access_token), json=payload
        )
        r.raise_for_status()
        repo = r.json()

    log.info("gitea.create_repo", repo_id=repo.get("id"), name=name)
    return {"repo": repo, "repo_id": repo.get("id")}


@register_node("gitea.list_issues")
async def gitea_list_issues(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List issues in a Gitea repository.

    config:
      base_url     — Gitea instance URL (required)
      access_token — Gitea access token (required)
      owner        — repository owner (required)
      repo         — repository name (required)
      state        — "open", "closed", or "all" (optional, default "open")
      limit        — max issues to return (optional, default 50)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    access_token = merged.get("access_token", "")
    owner = merged.get("owner")
    repo = merged.get("repo")

    if not base_url or not owner or not repo:
        raise ValueError("base_url, owner, and repo are required for gitea.list_issues")

    params = {
        "state": merged.get("state", "open"),
        "type": "issues",
        "limit": merged.get("limit", 50),
    }

    async with httpx.AsyncClient(base_url=_api_base(base_url), timeout=30) as client:
        r = await client.get(
            f"/repos/{owner}/{repo}/issues",
            headers=_gitea_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        issues = r.json()

    log.info("gitea.list_issues", owner=owner, repo=repo, count=len(issues))
    return {"issues": issues, "count": len(issues)}


@register_node("gitea.create_issue")
async def gitea_create_issue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an issue in a Gitea repository.

    config:
      base_url     — Gitea instance URL (required)
      access_token — Gitea access token (required)
      owner        — repository owner (required)
      repo         — repository name (required)
      title        — issue title (required)
      body         — issue body (optional)
      assignees    — list of assignee usernames (optional)
      labels       — list of label IDs (optional)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    access_token = merged.get("access_token", "")
    owner = merged.get("owner")
    repo = merged.get("repo")
    title = merged.get("title")

    if not base_url or not owner or not repo or not title:
        raise ValueError("base_url, owner, repo, and title are required for gitea.create_issue")

    payload: dict = {"title": title}
    if merged.get("body"):
        payload["body"] = merged["body"]
    if merged.get("assignees"):
        payload["assignees"] = merged["assignees"]
    if merged.get("labels"):
        payload["labels"] = merged["labels"]

    async with httpx.AsyncClient(base_url=_api_base(base_url), timeout=30) as client:
        r = await client.post(
            f"/repos/{owner}/{repo}/issues",
            headers=_gitea_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        issue = r.json()

    log.info("gitea.create_issue", issue_number=issue.get("number"), title=title)
    return {"issue": issue, "issue_number": issue.get("number")}


@register_node("gitea.list_branches")
async def gitea_list_branches(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List branches in a Gitea repository.

    config:
      base_url     — Gitea instance URL (required)
      access_token — Gitea access token (required)
      owner        — repository owner (required)
      repo         — repository name (required)
      limit        — max branches to return (optional, default 50)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    access_token = merged.get("access_token", "")
    owner = merged.get("owner")
    repo = merged.get("repo")

    if not base_url or not owner or not repo:
        raise ValueError("base_url, owner, and repo are required for gitea.list_branches")

    params = {"limit": merged.get("limit", 50)}

    async with httpx.AsyncClient(base_url=_api_base(base_url), timeout=30) as client:
        r = await client.get(
            f"/repos/{owner}/{repo}/branches",
            headers=_gitea_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        branches = r.json()

    log.info("gitea.list_branches", owner=owner, repo=repo, count=len(branches))
    return {"branches": branches, "count": len(branches)}


@register_node("gitea.create_release")
async def gitea_create_release(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a release in a Gitea repository.

    config:
      base_url       — Gitea instance URL (required)
      access_token   — Gitea access token (required)
      owner          — repository owner (required)
      repo           — repository name (required)
      tag_name       — Git tag for the release (required)
      name           — release name/title (optional)
      body           — release notes (optional)
      draft          — whether this is a draft release (optional, default False)
      prerelease     — whether this is a prerelease (optional, default False)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    access_token = merged.get("access_token", "")
    owner = merged.get("owner")
    repo = merged.get("repo")
    tag_name = merged.get("tag_name")

    if not base_url or not owner or not repo or not tag_name:
        raise ValueError(
            "base_url, owner, repo, and tag_name are required for gitea.create_release"
        )

    payload: dict = {
        "tag_name": tag_name,
        "name": merged.get("name", tag_name),
        "body": merged.get("body", ""),
        "draft": merged.get("draft", False),
        "prerelease": merged.get("prerelease", False),
    }

    async with httpx.AsyncClient(base_url=_api_base(base_url), timeout=30) as client:
        r = await client.post(
            f"/repos/{owner}/{repo}/releases",
            headers=_gitea_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        release = r.json()

    log.info("gitea.create_release", release_id=release.get("id"), tag=tag_name)
    return {"release": release, "release_id": release.get("id")}
