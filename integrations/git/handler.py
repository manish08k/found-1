"""
Git integration.

Provides local git operations using asyncio subprocesses to call the
system git binary. No external HTTP calls.

Credential fields:
  - repo_path  : Absolute path to the local git repository
  - remote_url : (optional) Remote URL for clone/push/pull operations
  - username   : (optional) Git username for authenticated remotes
  - password   : (optional) Git password / personal access token
  - author_name  : (optional) Commit author name
  - author_email : (optional) Commit author email
"""
import asyncio
import os
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> dict:
    if not credential_id:
        return {}
    creds = await get_credential_data(credential_id, db)
    return creds or {}


async def _run_git(*args: str, cwd: str = None, env: dict = None) -> dict:
    """
    Run a git subcommand asynchronously.
    Returns dict with stdout, stderr, returncode.
    """
    full_env = {**os.environ}
    if env:
        full_env.update(env)
    # Prevent interactive prompts
    full_env["GIT_TERMINAL_PROMPT"] = "0"

    log.debug("git.run", args=args, cwd=cwd)
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=full_env,
    )
    stdout, stderr = await proc.communicate()
    return {
        "stdout": stdout.decode("utf-8", errors="replace").strip(),
        "stderr": stderr.decode("utf-8", errors="replace").strip(),
        "returncode": proc.returncode,
    }


def _raise_if_failed(result: dict, operation: str) -> None:
    if result["returncode"] != 0:
        raise RuntimeError(
            f"git {operation} failed (exit {result['returncode']}): {result['stderr']}"
        )


def _inject_auth_in_url(url: str, username: str, password: str) -> str:
    """Embed credentials into an https:// remote URL."""
    if not url or not username:
        return url
    if url.startswith("https://"):
        import urllib.parse
        escaped_pass = urllib.parse.quote(password or "", safe="")
        escaped_user = urllib.parse.quote(username, safe="")
        return url.replace("https://", f"https://{escaped_user}:{escaped_pass}@", 1)
    return url


@register_node("git.clone")
async def git_clone(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Clone a remote git repository to a local path."""
    creds = await _get_creds(credential_id, db)

    remote_url = (
        config.get("remote_url")
        or input_data.get("remote_url")
        or creds.get("remote_url")
    )
    if not remote_url:
        raise ValueError("'remote_url' is required in config, input_data, or credential")

    dest_path = config.get("dest_path") or input_data.get("dest_path")
    if not dest_path:
        raise ValueError("'dest_path' (local destination directory) is required")

    branch = config.get("branch") or input_data.get("branch")
    depth = config.get("depth")  # shallow clone depth

    username = creds.get("username")
    password = creds.get("password")
    auth_url = _inject_auth_in_url(remote_url, username, password)

    args = ["clone"]
    if branch:
        args += ["--branch", branch]
    if depth:
        args += ["--depth", str(int(depth))]
    args += [auth_url, dest_path]

    log.info("git.clone", remote_url=remote_url, dest_path=dest_path, branch=branch)
    result = await _run_git(*args)
    _raise_if_failed(result, "clone")

    log.info("git.clone.done", dest_path=dest_path)
    return {
        "cloned": True,
        "remote_url": remote_url,
        "dest_path": dest_path,
        "branch": branch,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


@register_node("git.commit")
async def git_commit(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Stage files and create a git commit in the local repository."""
    creds = await _get_creds(credential_id, db)
    repo_path = (
        config.get("repo_path")
        or input_data.get("repo_path")
        or creds.get("repo_path")
    )
    if not repo_path:
        raise ValueError("'repo_path' is required")

    message = config.get("message") or input_data.get("message")
    if not message:
        raise ValueError("'message' (commit message) is required")

    # Files to stage; default to all changed files
    files = config.get("files") or input_data.get("files") or ["."]

    author_name = config.get("author_name") or creds.get("author_name")
    author_email = config.get("author_email") or creds.get("author_email")

    env = {}
    if author_name:
        env["GIT_AUTHOR_NAME"] = author_name
        env["GIT_COMMITTER_NAME"] = author_name
    if author_email:
        env["GIT_AUTHOR_EMAIL"] = author_email
        env["GIT_COMMITTER_EMAIL"] = author_email

    log.info("git.commit", repo_path=repo_path, message=message, files=files)

    # Stage files
    if isinstance(files, list):
        add_result = await _run_git("add", "--", *files, cwd=repo_path, env=env)
    else:
        add_result = await _run_git("add", "--", files, cwd=repo_path, env=env)
    _raise_if_failed(add_result, "add")

    # Create commit
    commit_result = await _run_git(
        "commit", "-m", message, cwd=repo_path, env=env
    )
    _raise_if_failed(commit_result, "commit")

    # Get the new commit hash
    rev_result = await _run_git("rev-parse", "HEAD", cwd=repo_path)
    commit_hash = rev_result["stdout"] if rev_result["returncode"] == 0 else None

    log.info("git.commit.done", repo_path=repo_path, commit_hash=commit_hash)
    return {
        "committed": True,
        "commit_hash": commit_hash,
        "message": message,
        "stdout": commit_result["stdout"],
    }


@register_node("git.push")
async def git_push(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Push local commits to a remote repository."""
    creds = await _get_creds(credential_id, db)
    repo_path = (
        config.get("repo_path")
        or input_data.get("repo_path")
        or creds.get("repo_path")
    )
    if not repo_path:
        raise ValueError("'repo_path' is required")

    remote = config.get("remote", "origin")
    branch = config.get("branch") or input_data.get("branch", "")
    force = config.get("force", False)
    set_upstream = config.get("set_upstream", False)

    args = ["push", remote]
    if branch:
        args.append(branch)
    if force:
        args.append("--force")
    if set_upstream:
        args += ["--set-upstream"]

    # Inject credentials into remote URL if provided
    username = creds.get("username")
    password = creds.get("password")
    env = {}
    if username and password:
        # Use git credential helper via env
        env["GIT_ASKPASS"] = "echo"
        # Set remote URL temporarily with auth baked in
        remote_url_result = await _run_git(
            "remote", "get-url", remote, cwd=repo_path
        )
        if remote_url_result["returncode"] == 0:
            auth_url = _inject_auth_in_url(
                remote_url_result["stdout"], username, password
            )
            await _run_git(
                "remote", "set-url", remote, auth_url, cwd=repo_path
            )

    log.info("git.push", repo_path=repo_path, remote=remote, branch=branch)
    result = await _run_git(*args, cwd=repo_path, env=env)
    _raise_if_failed(result, "push")

    log.info("git.push.done", repo_path=repo_path)
    return {
        "pushed": True,
        "remote": remote,
        "branch": branch,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


@register_node("git.pull")
async def git_pull(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Pull the latest changes from a remote repository."""
    creds = await _get_creds(credential_id, db)
    repo_path = (
        config.get("repo_path")
        or input_data.get("repo_path")
        or creds.get("repo_path")
    )
    if not repo_path:
        raise ValueError("'repo_path' is required")

    remote = config.get("remote", "origin")
    branch = config.get("branch") or input_data.get("branch", "")
    rebase = config.get("rebase", False)

    args = ["pull", remote]
    if branch:
        args.append(branch)
    if rebase:
        args.append("--rebase")

    log.info("git.pull", repo_path=repo_path, remote=remote, branch=branch)
    result = await _run_git(*args, cwd=repo_path)
    _raise_if_failed(result, "pull")

    log.info("git.pull.done", repo_path=repo_path)
    return {
        "pulled": True,
        "remote": remote,
        "branch": branch,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


@register_node("git.create_branch")
async def git_create_branch(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create (and optionally checkout) a new git branch."""
    creds = await _get_creds(credential_id, db)
    repo_path = (
        config.get("repo_path")
        or input_data.get("repo_path")
        or creds.get("repo_path")
    )
    if not repo_path:
        raise ValueError("'repo_path' is required")

    branch_name = config.get("branch_name") or input_data.get("branch_name")
    if not branch_name:
        raise ValueError("'branch_name' is required")

    start_point = config.get("start_point") or input_data.get("start_point", "HEAD")
    checkout = config.get("checkout", True)  # switch to the new branch

    log.info("git.create_branch", repo_path=repo_path, branch_name=branch_name)

    if checkout:
        result = await _run_git(
            "checkout", "-b", branch_name, start_point, cwd=repo_path
        )
        operation = "checkout -b"
    else:
        result = await _run_git(
            "branch", branch_name, start_point, cwd=repo_path
        )
        operation = "branch"

    _raise_if_failed(result, operation)

    log.info("git.create_branch.done", branch_name=branch_name)
    return {
        "branch_created": True,
        "branch_name": branch_name,
        "start_point": start_point,
        "checked_out": checkout,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }
