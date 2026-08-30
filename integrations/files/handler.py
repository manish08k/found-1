"""
File operation nodes — local filesystem utilities.

Covers:
  read_text, write_text, read_binary, write_binary, list_directory,
  delete, move, copy, exists, compress_zip, extract_zip,
  parse_csv, generate_csv

All path operations are validated to prevent directory traversal attacks.
"""
import base64
import csv
import io
import mimetypes
import os
import pathlib
import shutil
import zipfile
from copy import deepcopy
from typing import Any

import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


# ─── Path safety ──────────────────────────────────────────────────────────────

# Restrict operations to this root when FILE_ALLOWED_ROOT env var is set.
# If not set, any absolute path is accepted (operator responsibility).
_ALLOWED_ROOT: str | None = os.environ.get("FILE_ALLOWED_ROOT")


def _safe_path(path: str) -> pathlib.Path:
    """Resolve path and validate it doesn't escape the allowed root."""
    p = pathlib.Path(path).expanduser().resolve()
    if _ALLOWED_ROOT:
        allowed = pathlib.Path(_ALLOWED_ROOT).resolve()
        try:
            p.relative_to(allowed)
        except ValueError:
            raise ValueError(
                f"files: path '{p}' is outside the allowed root '{allowed}'"
            )
    return p


# ─── read_text ────────────────────────────────────────────────────────────────

@register_node("files.read_text")
async def files_read_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Read a local file as text."""
    path_str = config.get("path") or input_data.get("path")
    if not path_str:
        raise ValueError("files.read_text: 'path' is required")
    p = _safe_path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"files.read_text: path not found: {p}")
    encoding = config.get("encoding", "utf-8")
    content = p.read_text(encoding=encoding)
    return {"content": content, "path": str(p), "size": p.stat().st_size}


# ─── write_text ───────────────────────────────────────────────────────────────

@register_node("files.write_text")
async def files_write_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Write text to a local file."""
    path_str = config.get("path") or input_data.get("path")
    if not path_str:
        raise ValueError("files.write_text: 'path' is required")
    content = config.get("content") or input_data.get("content", "")
    p = _safe_path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    encoding = config.get("encoding", "utf-8")
    mode = "a" if config.get("append", False) else "w"
    p.open(mode, encoding=encoding).write(content)
    return {"path": str(p), "bytes_written": len(content.encode(encoding))}


# ─── read_binary ─────────────────────────────────────────────────────────────

@register_node("files.read_binary")
async def files_read_binary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Read a file as base64-encoded binary."""
    path_str = config.get("path") or input_data.get("path")
    if not path_str:
        raise ValueError("files.read_binary: 'path' is required")
    p = _safe_path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"files.read_binary: path not found: {p}")
    raw = p.read_bytes()
    content_type, _ = mimetypes.guess_type(str(p))
    return {
        "content_base64": base64.b64encode(raw).decode(),
        "content_type": content_type or "application/octet-stream",
        "size": len(raw),
        "path": str(p),
    }


# ─── write_binary ─────────────────────────────────────────────────────────────

@register_node("files.write_binary")
async def files_write_binary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Write base64-encoded content to a file."""
    path_str = config.get("path") or input_data.get("path")
    if not path_str:
        raise ValueError("files.write_binary: 'path' is required")
    content_b64 = config.get("content_base64") or input_data.get("content_base64")
    if not content_b64:
        raise ValueError("files.write_binary: 'content_base64' is required")
    p = _safe_path(path_str)
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(content_b64)
    p.write_bytes(raw)
    return {"path": str(p), "bytes_written": len(raw)}


# ─── list_directory ───────────────────────────────────────────────────────────

@register_node("files.list_directory")
async def files_list_directory(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List files in a directory, optionally filtered by glob pattern."""
    path_str = config.get("path") or input_data.get("path", ".")
    p = _safe_path(path_str)
    if not p.is_dir():
        raise ValueError(f"files.list_directory: not a directory: {p}")

    pattern = config.get("pattern", "*")
    recursive = config.get("recursive", False)

    if recursive:
        entries = list(p.rglob(pattern))
    else:
        entries = list(p.glob(pattern))

    files = []
    for entry in sorted(entries):
        stat = entry.stat()
        files.append({
            "name": entry.name,
            "path": str(entry),
            "size": stat.st_size if entry.is_file() else 0,
            "is_dir": entry.is_dir(),
        })
    return {"files": files, "count": len(files), "path": str(p)}


# ─── delete ───────────────────────────────────────────────────────────────────

@register_node("files.delete")
async def files_delete(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a file or directory."""
    path_str = config.get("path") or input_data.get("path")
    if not path_str:
        raise ValueError("files.delete: 'path' is required")
    p = _safe_path(path_str)
    recursive = config.get("recursive", False)

    if not p.exists():
        return {"deleted": False, "path": str(p), "reason": "not found"}

    if p.is_dir():
        if recursive:
            shutil.rmtree(p)
        else:
            p.rmdir()  # raises if non-empty
    else:
        p.unlink()

    return {"deleted": True, "path": str(p)}


# ─── move ─────────────────────────────────────────────────────────────────────

@register_node("files.move")
async def files_move(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Move or rename a file."""
    src_str = config.get("source") or input_data.get("source")
    dst_str = config.get("destination") or input_data.get("destination")
    if not src_str or not dst_str:
        raise ValueError("files.move: 'source' and 'destination' are required")
    src = _safe_path(src_str)
    dst = _safe_path(dst_str)
    if not src.exists():
        raise FileNotFoundError(f"files.move: source not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"source": str(src), "destination": str(dst)}


# ─── copy ─────────────────────────────────────────────────────────────────────

@register_node("files.copy")
async def files_copy(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Copy a file."""
    src_str = config.get("source") or input_data.get("source")
    dst_str = config.get("destination") or input_data.get("destination")
    if not src_str or not dst_str:
        raise ValueError("files.copy: 'source' and 'destination' are required")
    src = _safe_path(src_str)
    dst = _safe_path(dst_str)
    if not src.exists():
        raise FileNotFoundError(f"files.copy: source not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))
    return {"source": str(src), "destination": str(dst)}


# ─── exists ───────────────────────────────────────────────────────────────────

@register_node("files.exists")
async def files_exists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Check whether a path exists."""
    path_str = config.get("path") or input_data.get("path")
    if not path_str:
        raise ValueError("files.exists: 'path' is required")
    p = _safe_path(path_str)
    exists = p.exists()
    result: dict = {"exists": exists, "path": str(p)}
    if exists:
        result["is_dir"] = p.is_dir()
        result["is_file"] = p.is_file()
        result["size"] = p.stat().st_size if p.is_file() else 0
    return result


# ─── compress_zip ─────────────────────────────────────────────────────────────

@register_node("files.compress_zip")
async def files_compress_zip(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a ZIP archive from a list of file paths."""
    file_list = config.get("files") or input_data.get("files", [])
    output_path_str = config.get("output_path") or input_data.get("output_path")
    if not output_path_str:
        raise ValueError("files.compress_zip: 'output_path' is required")
    if not file_list:
        raise ValueError("files.compress_zip: 'files' list is empty")

    out_path = _safe_path(output_path_str)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    compression = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(out_path, "w", compression) as zf:
        for f in file_list:
            fp = _safe_path(f)
            if not fp.exists():
                raise FileNotFoundError(f"files.compress_zip: not found: {fp}")
            if fp.is_dir():
                for child in fp.rglob("*"):
                    zf.write(child, child.relative_to(fp.parent))
            else:
                zf.write(fp, fp.name)

    return {
        "output_path": str(out_path),
        "size": out_path.stat().st_size,
        "file_count": len(file_list),
    }


# ─── extract_zip ─────────────────────────────────────────────────────────────

@register_node("files.extract_zip")
async def files_extract_zip(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Extract a ZIP archive to a directory."""
    path_str = config.get("path") or input_data.get("path")
    output_dir_str = config.get("output_dir") or input_data.get("output_dir")
    if not path_str or not output_dir_str:
        raise ValueError("files.extract_zip: 'path' and 'output_dir' are required")

    zip_path = _safe_path(path_str)
    out_dir = _safe_path(output_dir_str)

    if not zip_path.exists():
        raise FileNotFoundError(f"files.extract_zip: not found: {zip_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Validate members don't escape output_dir (zip slip protection)
        for member in zf.namelist():
            member_path = (out_dir / member).resolve()
            try:
                member_path.relative_to(out_dir.resolve())
            except ValueError:
                raise ValueError(f"files.extract_zip: dangerous path in archive: {member}")
        zf.extractall(out_dir)
        names = zf.namelist()

    return {"output_dir": str(out_dir), "extracted_files": names, "file_count": len(names)}


# ─── parse_csv ────────────────────────────────────────────────────────────────

@register_node("files.parse_csv")
async def files_parse_csv(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse CSV from text content or a file path."""
    content = config.get("content") or input_data.get("content")
    if not content:
        path_str = config.get("path") or input_data.get("path")
        if not path_str:
            raise ValueError("files.parse_csv: provide 'content' or 'path'")
        p = _safe_path(path_str)
        content = p.read_text(encoding=config.get("encoding", "utf-8"))

    delimiter = config.get("delimiter", ",")
    has_header = config.get("has_header", True)
    buf = io.StringIO(content)

    if has_header:
        reader = csv.DictReader(buf, delimiter=delimiter)
        items = [dict(row) for row in reader]
    else:
        reader_plain = csv.reader(buf, delimiter=delimiter)
        items = [row for row in reader_plain]

    return {"items": items, "count": len(items)}


# ─── generate_csv ─────────────────────────────────────────────────────────────

@register_node("files.generate_csv")
async def files_generate_csv(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate CSV text from an array of dicts."""
    data = config.get("data") or input_data.get("data") or input_data.get("items", [])
    if not isinstance(data, list):
        raise ValueError("files.generate_csv: 'data' must be a list")

    delimiter = config.get("delimiter", ",")
    fields = config.get("fields")
    if not fields and data and isinstance(data[0], dict):
        fields = list(data[0].keys())
    if not fields:
        raise ValueError("files.generate_csv: cannot determine fields from empty data")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, delimiter=delimiter, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        writer.writerow(row if isinstance(row, dict) else {})

    csv_str = buf.getvalue()
    result: dict = {"csv": csv_str, "row_count": len(data)}

    # Optionally write to file
    out_path_str = config.get("output_path")
    if out_path_str:
        out_path = _safe_path(out_path_str)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(csv_str, encoding="utf-8")
        result["output_path"] = str(out_path)

    return result
