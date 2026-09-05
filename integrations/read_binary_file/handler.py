"""
ReadBinaryFile integration.

Reads a single binary file from the local filesystem and returns its
contents as a base64-encoded string along with metadata.

No credentials required.

Config fields:
  - file_path (required): Absolute or relative path to the file to read.
"""
import base64
import mimetypes
import structlog
from pathlib import Path

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — imported for consistency

log = structlog.get_logger(__name__)


@register_node("read_binary_file.read")
async def read_binary_file_read(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Read a binary file from local disk and return its content as base64.

    Params:
      - file_path (required): Path to the file to read. Can be absolute or
        relative to the current working directory.

    Returns:
      - content_base64: Base64-encoded file content.
      - size: File size in bytes.
      - mime_type: Detected MIME type (e.g. 'image/png', 'application/pdf').
      - file_name: Bare file name (e.g. 'report.pdf').
    """
    file_path = config.get("file_path") or input_data.get("file_path")
    if not file_path:
        raise ValueError("read_binary_file.read requires 'file_path'")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    raw = path.read_bytes()
    size = len(raw)
    content_base64 = base64.b64encode(raw).decode("utf-8")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = "application/octet-stream"

    file_name = path.name

    log.info("read_binary_file.read", file_path=str(path), size=size, mime_type=mime_type)
    return {
        "content_base64": content_base64,
        "size": size,
        "mime_type": mime_type,
        "file_name": file_name,
    }
