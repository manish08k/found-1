"""
Nextcloud file storage integration (WebDAV).

Auth: HTTP Basic (username + password) against a Nextcloud instance.

Credential fields:
  - base_url:  Nextcloud instance URL (e.g. https://cloud.example.com)
  - username:  Nextcloud username
  - password:  Nextcloud password or app password

WebDAV base: {base_url}/remote.php/dav/files/{username}/

Nodes:
  - nextcloud.list_files      — list files/folders at a path
  - nextcloud.upload_file     — upload file content to a path
  - nextcloud.download_file   — download file content from a path
  - nextcloud.create_folder   — create a directory (MKCOL)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_PROPFIND_BODY = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<d:propfind xmlns:d="DAV:">'
    "<d:prop>"
    "<d:displayname/><d:getcontentlength/><d:getcontenttype/>"
    "<d:getlastmodified/><d:resourcetype/>"
    "</d:prop>"
    "</d:propfind>"
)


async def _webdav_client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """Return (AsyncClient, dav_root) for Nextcloud WebDAV."""
    creds = await get_credential_data(credential_id, db)
    base_url = (creds.get("base_url") or "").rstrip("/")
    username = creds.get("username")
    password = creds.get("password")
    if not base_url:
        raise ValueError("Nextcloud credential missing 'base_url'")
    if not username:
        raise ValueError("Nextcloud credential missing 'username'")
    if not password:
        raise ValueError("Nextcloud credential missing 'password'")

    dav_root = f"{base_url}/remote.php/dav/files/{username}"
    client = httpx.AsyncClient(
        auth=(username, password),
        timeout=60.0,
    )
    return client, dav_root


def _check(r: httpx.Response, expected: int | None = None) -> dict:
    ok = (r.status_code == expected) if expected else r.is_success
    if not ok:
        raise ValueError(f"Nextcloud WebDAV error {r.status_code}: {r.text[:200]}")
    if not r.content or r.headers.get("content-type", "").startswith("application/xml"):
        return {"status": r.status_code, "body": r.text}
    try:
        return r.json()
    except Exception:
        return {"status": r.status_code, "body": r.text}


@register_node("nextcloud.list_files")
async def list_files(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    PROPFIND — list files and folders at a given path.

    Config:
      path  — remote path relative to user root (default: /)
      depth — 0 | 1 | infinity (default: 1)
    """
    path = (config.get("path") or input_data.get("path") or "").strip("/")
    depth = str(config.get("depth") if config.get("depth") is not None else input_data.get("depth") or 1)

    log.info("nextcloud.list_files", path=path, depth=depth)
    async with await _webdav_client(credential_id, db) as (client, dav_root):
        url = f"{dav_root}/{path}" if path else dav_root
        r = await client.request(
            "PROPFIND",
            url,
            content=_PROPFIND_BODY.encode(),
            headers={"Depth": depth, "Content-Type": "application/xml"},
        )
    return _check(r)


@register_node("nextcloud.upload_file")
async def upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    PUT — upload file content to a remote path.

    Config:
      path         — (required) remote destination path (e.g. /docs/report.pdf)
      content      — file content as string or bytes
      content_type — MIME type (default: application/octet-stream)
    """
    path = (config.get("path") or input_data.get("path") or "").strip("/")
    if not path:
        raise ValueError("nextcloud.upload_file requires 'path'")

    content = config.get("content") if config.get("content") is not None else input_data.get("content", "")
    content_type = (
        config.get("content_type")
        or input_data.get("content_type")
        or "application/octet-stream"
    )

    if isinstance(content, str):
        raw = content.encode()
    else:
        raw = bytes(content)

    log.info("nextcloud.upload_file", path=path, bytes=len(raw))
    async with await _webdav_client(credential_id, db) as (client, dav_root):
        r = await client.put(
            f"{dav_root}/{path}",
            content=raw,
            headers={"Content-Type": content_type},
        )
    return _check(r)


@register_node("nextcloud.download_file")
async def download_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET — download file content from a remote path.

    Config:
      path — (required) remote file path (e.g. /docs/report.pdf)

    Returns:
      content      — file content as UTF-8 string (or base64 for binary)
      content_type — MIME type from response
      size         — byte length
    """
    path = (config.get("path") or input_data.get("path") or "").strip("/")
    if not path:
        raise ValueError("nextcloud.download_file requires 'path'")

    log.info("nextcloud.download_file", path=path)
    async with await _webdav_client(credential_id, db) as (client, dav_root):
        r = await client.get(f"{dav_root}/{path}")

    if not r.is_success:
        raise ValueError(f"Nextcloud download error {r.status_code}: {r.text[:200]}")

    content_type = r.headers.get("content-type", "application/octet-stream")
    try:
        body = r.text
    except Exception:
        import base64
        body = base64.b64encode(r.content).decode()

    return {
        "content": body,
        "content_type": content_type,
        "size": len(r.content),
        "path": path,
    }


@register_node("nextcloud.create_folder")
async def create_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    MKCOL — create a directory on Nextcloud.

    Config:
      path — (required) remote folder path to create (e.g. /projects/2024)
    """
    path = (config.get("path") or input_data.get("path") or "").strip("/")
    if not path:
        raise ValueError("nextcloud.create_folder requires 'path'")

    log.info("nextcloud.create_folder", path=path)
    async with await _webdav_client(credential_id, db) as (client, dav_root):
        r = await client.request("MKCOL", f"{dav_root}/{path}")
    # 201 Created or 405 Method Not Allowed (already exists)
    if r.status_code not in (201, 405):
        raise ValueError(f"Nextcloud MKCOL error {r.status_code}: {r.text[:200]}")
    return {"status": r.status_code, "path": path, "created": r.status_code == 201}


async def test_connection(creds: dict) -> None:
    """Verify Nextcloud credentials by doing a shallow PROPFIND on the root."""
    base_url = (creds.get("base_url") or "").rstrip("/")
    username = creds.get("username")
    password = creds.get("password")
    if not base_url or not username or not password:
        raise ValueError("Nextcloud requires 'base_url', 'username', and 'password'")
    dav_root = f"{base_url}/remote.php/dav/files/{username}"
    async with httpx.AsyncClient(auth=(username, password), timeout=15.0) as client:
        r = await client.request(
            "PROPFIND",
            dav_root,
            content=_PROPFIND_BODY.encode(),
            headers={"Depth": "0", "Content-Type": "application/xml"},
        )
    if r.status_code not in (200, 207):
        raise ValueError(f"Nextcloud connection failed: {r.status_code}")
