"""
Bitbucket repository and pull request integration.

Provides repo listing, issue creation, PR creation, and commit listing
via the Bitbucket Cloud REST API 2.0.

Credential fields (one of two auth modes):
  Mode 1 — Basic auth:
    - username     : Bitbucket username or email.
    - app_password : Bitbucket App Password with required scopes.
  Mode 2 — OAuth / access token:
    - access_token : A valid OAuth2 access token.

Base URL: https://api.bitbucket.org/2.0/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.bitbucket.org/2.0"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    username = creds.get("username")
    app_password = creds.get("app_password")

    if access_token:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        auth = None
    elif username and app_password:
        headers = {"Content-Type": "application/json"}
        auth = (username, app_password)
    else:
        raise ValueError(
            "Bitbucket credential requires either 'access_token' or both 'username' and 'app_password'"
        )

    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers=headers,
        auth=auth,
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Bitbucket API error {r.status_code}: {detail}")


@register_node("bitbucket.list_repos")
async def bb_list_repos(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List repositories for a workspace.

    Params:
      - workspace (required): Workspace slug or UUID.
      - page: Page number (default 1).
      - pagelen: Results per page (max 100, default 25).
      - q: Query string to filter repos (Bitbucket query syntax).
      - sort: Field to sort by (e.g. 'name', '-updated_on').
    """
    workspace = config.get("workspace") or input_data.get("workspace")
    if not workspace:
        raise ValueError("bitbucket.list_repos requires 'workspace'")

    page = int(config.get("page") or input_data.get("page", 1))
    pagelen = min(int(config.get("pagelen") or input_data.get("pagelen", 25)), 100)
    q = config.get("q") or input_data.get("q")
    sort = config.get("sort") or input_data.get("sort")

    params: dict = {"page": page, "pagelen": pagelen}
    if q:
        params["q"] = q
    if sort:
        params["sort"] = sort

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/repositories/{workspace}", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("bitbucket.list_repos", workspace=workspace, size=data.get("size", 0))
    return {
        "repos": data.get("values", []),
        "size": data.get("size", 0),
        "next": data.get("next"),
    }


@register_node("bitbucket.create_issue")
async def bb_create_issue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create an issue in a Bitbucket repository.

    Params:
      - workspace (required): Workspace slug or UUID.
      - repo_slug (required): Repository slug.
      - title (required): Issue title.
      - content: Issue description (plain text or markup).
      - kind: 'bug', 'enhancement', 'proposal', 'task' (default 'bug').
      - priority: 'trivial', 'minor', 'major', 'critical', 'blocker' (default 'major').
      - component: Component name string.
      - milestone: Milestone name string.
      - version: Version name string.
      - assignee: Username to assign the issue to.
    """
    workspace = config.get("workspace") or input_data.get("workspace")
    repo_slug = config.get("repo_slug") or input_data.get("repo_slug")
    title = config.get("title") or input_data.get("title")
    if not workspace:
        raise ValueError("bitbucket.create_issue requires 'workspace'")
    if not repo_slug:
        raise ValueError("bitbucket.create_issue requires 'repo_slug'")
    if not title:
        raise ValueError("bitbucket.create_issue requires 'title'")

    payload: dict = {
        "title": title,
        "kind": config.get("kind") or input_data.get("kind", "bug"),
        "priority": config.get("priority") or input_data.get("priority", "major"),
    }

    content = config.get("content") or input_data.get("content")
    if content:
        payload["content"] = {"raw": content}

    for field in ("component", "milestone", "version"):
        val = config.get(field) or input_data.get(field)
        if val:
            payload[field] = {"name": val}

    assignee = config.get("assignee") or input_data.get("assignee")
    if assignee:
        payload["assignee"] = {"nickname": assignee}

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/repositories/{workspace}/{repo_slug}/issues",
            json=payload,
        )
        _raise_for_status(r)
        data = r.json()

    log.info("bitbucket.create_issue", workspace=workspace, repo=repo_slug, issue_id=data.get("id"))
    return {"issue": data, "id": data.get("id"), "title": data.get("title")}


@register_node("bitbucket.create_pr")
async def bb_create_pr(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a pull request in a Bitbucket repository.

    Params:
      - workspace (required): Workspace slug or UUID.
      - repo_slug (required): Repository slug.
      - title (required): PR title.
      - source_branch (required): Name of the source branch.
      - destination_branch: Name of the destination branch (default 'main').
      - description: PR description.
      - close_source_branch: bool — close source branch on merge.
      - reviewers: Comma-separated list of reviewer usernames.
    """
    workspace = config.get("workspace") or input_data.get("workspace")
    repo_slug = config.get("repo_slug") or input_data.get("repo_slug")
    title = config.get("title") or input_data.get("title")
    source_branch = config.get("source_branch") or input_data.get("source_branch")
    if not workspace:
        raise ValueError("bitbucket.create_pr requires 'workspace'")
    if not repo_slug:
        raise ValueError("bitbucket.create_pr requires 'repo_slug'")
    if not title:
        raise ValueError("bitbucket.create_pr requires 'title'")
    if not source_branch:
        raise ValueError("bitbucket.create_pr requires 'source_branch'")

    destination_branch = config.get("destination_branch") or input_data.get("destination_branch", "main")

    payload: dict = {
        "title": title,
        "source": {"branch": {"name": source_branch}},
        "destination": {"branch": {"name": destination_branch}},
        "close_source_branch": bool(config.get("close_source_branch") or input_data.get("close_source_branch", False)),
    }

    description = config.get("description") or input_data.get("description")
    if description:
        payload["description"] = description

    reviewers_raw = config.get("reviewers") or input_data.get("reviewers", "")
    if reviewers_raw:
        reviewer_list = [r.strip() for r in str(reviewers_raw).split(",") if r.strip()]
        payload["reviewers"] = [{"nickname": rv} for rv in reviewer_list]

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/repositories/{workspace}/{repo_slug}/pullrequests",
            json=payload,
        )
        _raise_for_status(r)
        data = r.json()

    log.info("bitbucket.create_pr", workspace=workspace, repo=repo_slug, pr_id=data.get("id"))
    return {"pr": data, "id": data.get("id"), "links": data.get("links", {})}


@register_node("bitbucket.list_commits")
async def bb_list_commits(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List commits in a repository, optionally filtered by branch.

    Params:
      - workspace (required): Workspace slug or UUID.
      - repo_slug (required): Repository slug.
      - branch: Branch name or revision to filter by.
      - pagelen: Results per page (max 100, default 30).
      - page: Page number (default 1).
      - include: Include only files matching this path pattern.
      - exclude: Exclude files matching this path pattern.
    """
    workspace = config.get("workspace") or input_data.get("workspace")
    repo_slug = config.get("repo_slug") or input_data.get("repo_slug")
    if not workspace:
        raise ValueError("bitbucket.list_commits requires 'workspace'")
    if not repo_slug:
        raise ValueError("bitbucket.list_commits requires 'repo_slug'")

    branch = config.get("branch") or input_data.get("branch")
    pagelen = min(int(config.get("pagelen") or input_data.get("pagelen", 30)), 100)
    page = int(config.get("page") or input_data.get("page", 1))

    params: dict = {"pagelen": pagelen, "page": page}
    for field in ("include", "exclude"):
        val = config.get(field) or input_data.get(field)
        if val:
            params[field] = val

    url = f"/repositories/{workspace}/{repo_slug}/commits"
    if branch:
        url = f"{url}/{branch}"

    async with await _client(credential_id, db) as client:
        r = await client.get(url, params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "commits": data.get("values", []),
        "next": data.get("next"),
        "pagelen": data.get("pagelen"),
    }


@register_node("bitbucket.list_prs")
async def bb_list_prs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List pull requests for a repository.

    Params:
      - workspace (required): Workspace slug or UUID.
      - repo_slug (required): Repository slug.
      - state: 'OPEN', 'MERGED', 'DECLINED', 'SUPERSEDED' (default 'OPEN').
      - pagelen: Results per page (max 50, default 20).
    """
    workspace = config.get("workspace") or input_data.get("workspace")
    repo_slug = config.get("repo_slug") or input_data.get("repo_slug")
    if not workspace:
        raise ValueError("bitbucket.list_prs requires 'workspace'")
    if not repo_slug:
        raise ValueError("bitbucket.list_prs requires 'repo_slug'")

    state = config.get("state") or input_data.get("state", "OPEN")
    pagelen = min(int(config.get("pagelen") or input_data.get("pagelen", 20)), 50)

    params = {"state": state, "pagelen": pagelen}

    async with await _client(credential_id, db) as client:
        r = await client.get(
            f"/repositories/{workspace}/{repo_slug}/pullrequests",
            params=params,
        )
        _raise_for_status(r)
        data = r.json()

    return {
        "pull_requests": data.get("values", []),
        "size": data.get("size", 0),
        "next": data.get("next"),
    }
