"""
FTP integration.

Provides file listing, upload, download, and deletion against FTP servers
using Python's standard library ftplib wrapped in asyncio executor calls.

Credential fields:
  - host     : FTP server hostname or IP
  - port     : FTP server port (default 21)
  - username : FTP username (default 'anonymous')
  - password : FTP password (default '')
  - use_tls  : (optional bool) use FTPS (explicit TLS) if true
"""
import asyncio
import ftplib
import io
import os
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    if not creds.get("host"):
        raise ValueError("FTP credential missing 'host'")
    return creds


def _make_ftp(creds: dict) -> ftplib.FTP:
    host = creds["host"]
    port = int(creds.get("port", 21))
    username = creds.get("username", "anonymous")
    password = creds.get("password", "")
    use_tls = creds.get("use_tls", False)

    if use_tls:
        ftp = ftplib.FTP_TLS()
    else:
        ftp = ftplib.FTP()

    ftp.connect(host, port, timeout=30)
    ftp.login(username, password)
    if use_tls:
        ftp.prot_p()  # switch to secure data connection

    ftp.set_pasv(True)
    return ftp


async def _run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


def _ftp_list_files(creds: dict, path: str) -> list:
    ftp = _make_ftp(creds)
    try:
        items = []
        ftp.cwd(path)
        raw = []
        ftp.retrlines("LIST -la", raw.append)
        for line in raw:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            perms, _, _, _, size, month, day, year_or_time, name = parts
            if name in (".", ".."):
                continue
            items.append({
                "name": name,
                "size": int(size) if size.isdigit() else 0,
                "permissions": perms,
                "type": "directory" if perms.startswith("d") else "file",
                "modified": f"{month} {day} {year_or_time}",
                "path": os.path.join(path, name),
            })
        return items
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


def _ftp_download_file(creds: dict, remote_path: str) -> bytes:
    ftp = _make_ftp(creds)
    try:
        buf = io.BytesIO()
        ftp.retrbinary(f"RETR {remote_path}", buf.write)
        return buf.getvalue()
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


def _ftp_upload_file(creds: dict, remote_path: str, content: bytes) -> bool:
    ftp = _make_ftp(creds)
    try:
        buf = io.BytesIO(content)
        ftp.storbinary(f"STOR {remote_path}", buf)
        return True
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


def _ftp_delete_file(creds: dict, remote_path: str) -> bool:
    ftp = _make_ftp(creds)
    try:
        ftp.delete(remote_path)
        return True
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()


@register_node("ftp.list_files")
async def list_files(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List files and directories at the given FTP path."""
    creds = await _get_creds(credential_id, db)
    path = config.get("path") or input_data.get("path", "/")
    log.info("ftp.list_files", host=creds["host"], path=path)

    items = await _run_in_executor(_ftp_list_files, creds, path)

    # Apply optional type filter
    filter_type = config.get("filter_type")  # "file" or "directory"
    if filter_type:
        items = [i for i in items if i["type"] == filter_type]

    log.info("ftp.list_files.done", path=path, count=len(items))
    return {"files": items, "count": len(items), "path": path}


@register_node("ftp.upload_file")
async def upload_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Upload content to a remote FTP path."""
    creds = await _get_creds(credential_id, db)
    remote_path = config.get("remote_path") or input_data.get("remote_path")
    if not remote_path:
        raise ValueError("'remote_path' is required in config or input_data")

    # Content can come as bytes, str, or base64-encoded string
    content = config.get("content") or input_data.get("content")
    if content is None:
        raise ValueError("'content' is required")

    encoding = config.get("encoding", "utf-8")
    if isinstance(content, str):
        import base64
        if config.get("base64_encoded"):
            raw_bytes = base64.b64decode(content)
        else:
            raw_bytes = content.encode(encoding)
    elif isinstance(content, bytes):
        raw_bytes = content
    else:
        raise ValueError("'content' must be a str or bytes value")

    log.info("ftp.upload_file", host=creds["host"], remote_path=remote_path, size=len(raw_bytes))

    await _run_in_executor(_ftp_upload_file, creds, remote_path, raw_bytes)

    log.info("ftp.upload_file.done", remote_path=remote_path)
    return {"uploaded": True, "remote_path": remote_path, "bytes_written": len(raw_bytes)}


@register_node("ftp.download_file")
async def download_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Download a file from the FTP server."""
    creds = await _get_creds(credential_id, db)
    remote_path = config.get("remote_path") or input_data.get("remote_path")
    if not remote_path:
        raise ValueError("'remote_path' is required in config or input_data")

    as_base64 = config.get("as_base64", True)
    encoding = config.get("encoding", "utf-8")

    log.info("ftp.download_file", host=creds["host"], remote_path=remote_path)

    raw_bytes = await _run_in_executor(_ftp_download_file, creds, remote_path)

    if as_base64:
        import base64
        content = base64.b64encode(raw_bytes).decode("ascii")
        content_type = "base64"
    else:
        try:
            content = raw_bytes.decode(encoding)
            content_type = "text"
        except UnicodeDecodeError:
            import base64
            content = base64.b64encode(raw_bytes).decode("ascii")
            content_type = "base64"

    log.info("ftp.download_file.done", remote_path=remote_path, size=len(raw_bytes))
    return {
        "content": content,
        "content_type": content_type,
        "size": len(raw_bytes),
        "remote_path": remote_path,
    }


@register_node("ftp.delete_file")
async def delete_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a file from the FTP server."""
    creds = await _get_creds(credential_id, db)
    remote_path = config.get("remote_path") or input_data.get("remote_path")
    if not remote_path:
        raise ValueError("'remote_path' is required in config or input_data")

    log.info("ftp.delete_file", host=creds["host"], remote_path=remote_path)

    await _run_in_executor(_ftp_delete_file, creds, remote_path)

    log.info("ftp.delete_file.done", remote_path=remote_path)
    return {"deleted": True, "remote_path": remote_path}
