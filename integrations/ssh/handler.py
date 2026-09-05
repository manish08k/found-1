"""SSH integration — remote command execution, file upload/download."""
import structlog
import httpx  # noqa: F401 — standard import kept for consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

try:
    import asyncssh
    _ASYNCSSH_AVAILABLE = True
except ImportError:
    asyncssh = None  # type: ignore
    _ASYNCSSH_AVAILABLE = False


async def _get_connect_kwargs(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    kwargs = {
        "host": creds["host"],
        "port": int(creds.get("port", 22)),
        "username": creds["username"],
        "known_hosts": None,
    }
    if creds.get("private_key"):
        kwargs["client_keys"] = [asyncssh.import_private_key(creds["private_key"])]
    else:
        kwargs["password"] = creds.get("password", "")
    return kwargs


@register_node("ssh.execute_command")
async def ssh_execute_command(config: dict, input_data: dict, credential_id: str, db) -> dict:
    if not _ASYNCSSH_AVAILABLE:
        raise RuntimeError("asyncssh is not installed. Install it with: pip install asyncssh")

    command = config.get("command") or input_data.get("command", "")
    timeout = config.get("timeout", 30)

    connect_kwargs = await _get_connect_kwargs(credential_id, db)
    log.info("ssh.execute_command", host=connect_kwargs["host"], command=command[:80])

    async with asyncssh.connect(**connect_kwargs) as conn:
        result = await asyncio_wait_for_compat(
            conn.run(command, timeout=timeout)
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_status": result.exit_status,
            "command": command,
        }


@register_node("ssh.upload_file")
async def ssh_upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    if not _ASYNCSSH_AVAILABLE:
        raise RuntimeError("asyncssh is not installed. Install it with: pip install asyncssh")

    local_path = config.get("local_path") or input_data.get("local_path", "")
    remote_path = config.get("remote_path") or input_data.get("remote_path", "")

    connect_kwargs = await _get_connect_kwargs(credential_id, db)
    log.info("ssh.upload_file", host=connect_kwargs["host"], local=local_path, remote=remote_path)

    async with asyncssh.connect(**connect_kwargs) as conn:
        async with conn.start_sftp_client() as sftp:
            await sftp.put(local_path, remote_path)

    return {"local_path": local_path, "remote_path": remote_path, "status": "uploaded"}


@register_node("ssh.download_file")
async def ssh_download_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    if not _ASYNCSSH_AVAILABLE:
        raise RuntimeError("asyncssh is not installed. Install it with: pip install asyncssh")

    remote_path = config.get("remote_path") or input_data.get("remote_path", "")
    local_path = config.get("local_path") or input_data.get("local_path", "")

    connect_kwargs = await _get_connect_kwargs(credential_id, db)
    log.info("ssh.download_file", host=connect_kwargs["host"], remote=remote_path, local=local_path)

    async with asyncssh.connect(**connect_kwargs) as conn:
        async with conn.start_sftp_client() as sftp:
            await sftp.get(remote_path, local_path)

    return {"remote_path": remote_path, "local_path": local_path, "status": "downloaded"}


# asyncssh.run returns a coroutine that may or may not need extra awaiting
# depending on the version — helper keeps things tidy
async def asyncio_wait_for_compat(coro):
    import asyncio
    return await asyncio.ensure_future(coro)
