"""WriteBinaryFile integration — write or append binary/text content to disk."""
import base64
import os
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _prepare_content(raw_content, encoding: str) -> bytes:
    """Convert raw_content to bytes according to encoding mode."""
    if encoding == "binary":
        if isinstance(raw_content, bytes):
            return raw_content
        return base64.b64decode(raw_content)
    else:
        enc = encoding if encoding else "utf-8"
        if isinstance(raw_content, bytes):
            return raw_content
        return raw_content.encode(enc)


@register_node("write_binary_file.write")
async def write_binary_file_write(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Write content to a file, overwriting any existing file.

    config:
      file_path — destination path on disk (required)
      content   — string or base64-encoded bytes to write (required)
      encoding  — "utf-8" (default) for text, or "binary" to base64-decode content
    """
    merged = {**config, **input_data}
    file_path = merged.get("file_path")
    if not file_path:
        raise ValueError("file_path is required for write_binary_file.write")

    raw_content = merged.get("content", "")
    encoding = merged.get("encoding", "utf-8")

    content_bytes = _prepare_content(raw_content, encoding)

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    with open(file_path, "wb") as fh:
        fh.write(content_bytes)

    bytes_written = len(content_bytes)
    log.info("write_binary_file.write", file_path=file_path, bytes_written=bytes_written)
    return {"written": True, "file_path": file_path, "bytes_written": bytes_written}


@register_node("write_binary_file.append")
async def write_binary_file_append(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Append content to an existing file (creates file if it does not exist).

    config:
      file_path — destination path on disk (required)
      content   — string or base64-encoded bytes to append (required)
      encoding  — "utf-8" (default) for text, or "binary" to base64-decode content
    """
    merged = {**config, **input_data}
    file_path = merged.get("file_path")
    if not file_path:
        raise ValueError("file_path is required for write_binary_file.append")

    raw_content = merged.get("content", "")
    encoding = merged.get("encoding", "utf-8")

    content_bytes = _prepare_content(raw_content, encoding)

    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    with open(file_path, "ab") as fh:
        fh.write(content_bytes)

    bytes_written = len(content_bytes)
    log.info("write_binary_file.append", file_path=file_path, bytes_written=bytes_written)
    return {"appended": True, "file_path": file_path, "bytes_written": bytes_written}
