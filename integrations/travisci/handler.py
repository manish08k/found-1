"""
Travis CI integration.

Provides repository listing, build management, and build triggering
via the Travis CI API v3 with token Bearer authentication.

Credential fields:
  - token : Travis CI API token
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.travis-ci.com/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    token = creds.get("token")
    if not token:
        raise ValueError("Travis CI credential missing 'token'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Travis-CI-Token": token,
            "Authorization": f"token {token}",
            "Travis-API-Version": "3",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Travis CI API error {r.status_code}: {detail}")


@register_node("travisci.list_repos")
async def travis_list_repos(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List repositories accessible via Travis CI."""
    limit = int(config.get("limit") or input_data.get("limit", 25))
    offset = int(config.get("offset") or input_data.get("offset", 0))
    active = config.get("active") or input_data.get("active")

    params: dict = {"limit": limit, "offset": offset}
    if active is not None:
        params["repository.active"] = str(active).lower()

    async with await _client(credential_id, db) as client:
        r = await client.get("repos", params=params)
        _raise_for_status(r)
        data = r.json()

    repos = data.get("repositories", [])
    log.info("travisci.list_repos", count=len(repos))
    return {"repositories": repos, "pagination": data.get("@pagination", {})}


@register_node("travisci.get_build")
async def travis_get_build(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get details of a specific Travis CI build."""
    build_id = config.get("build_id") or input_data.get("build_id")
    if not build_id:
        raise ValueError("travisci.get_build requires 'build_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"build/{build_id}", params={"include": "build.jobs"})
        _raise_for_status(r)
        data = r.json()

    log.info("travisci.get_build", build_id=build_id, state=data.get("state"))
    return {"build": data}


@register_node("travisci.trigger_build")
async def travis_trigger_build(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Trigger a new Travis CI build for a repository branch."""
    repo_slug = config.get("repo_slug") or input_data.get("repo_slug")
    branch = config.get("branch") or input_data.get("branch", "main")
    message = config.get("message") or input_data.get("message", "Triggered via automation")
    env_vars = config.get("env_vars") or input_data.get("env_vars", {})

    if not repo_slug:
        raise ValueError("travisci.trigger_build requires 'repo_slug' (e.g. 'owner/repo')")

    # URL-encode the slug
    encoded_slug = repo_slug.replace("/", "%2F")

    payload: dict = {
        "request": {
            "branch": branch,
            "message": message,
        }
    }
    if env_vars and isinstance(env_vars, dict):
        payload["request"]["config"] = {
            "env": {"global": [f"{k}={v}" for k, v in env_vars.items()]}
        }

    async with await _client(credential_id, db) as client:
        r = await client.post(f"repo/{encoded_slug}/requests", json=payload)
        _raise_for_status(r)
        data = r.json()

    request_id = data.get("request", {}).get("id") or data.get("@href", "")
    log.info("travisci.trigger_build", repo=repo_slug, branch=branch, request_id=request_id)
    return {"request": data.get("request", data), "request_id": request_id}


@register_node("travisci.list_builds")
async def travis_list_builds(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List builds for a repository."""
    repo_slug = config.get("repo_slug") or input_data.get("repo_slug")
    limit = int(config.get("limit") or input_data.get("limit", 25))
    offset = int(config.get("offset") or input_data.get("offset", 0))
    state = config.get("state") or input_data.get("state")
    branch = config.get("branch") or input_data.get("branch")

    if not repo_slug:
        raise ValueError("travisci.list_builds requires 'repo_slug'")

    encoded_slug = repo_slug.replace("/", "%2F")
    params: dict = {"limit": limit, "offset": offset}
    if state:
        params["build.state"] = state
    if branch:
        params["build.branch.name"] = branch

    async with await _client(credential_id, db) as client:
        r = await client.get(f"repo/{encoded_slug}/builds", params=params)
        _raise_for_status(r)
        data = r.json()

    builds = data.get("builds", [])
    log.info("travisci.list_builds", repo=repo_slug, count=len(builds))
    return {"builds": builds, "pagination": data.get("@pagination", {})}
