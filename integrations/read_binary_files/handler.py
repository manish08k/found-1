"""
ReadBinaryFiles integration.

Reads multiple binary files from a directory (with optional glob pattern
and recursive traversal) and returns their contents as base64-encoded strings.

No credentials required.

Config fields:
  - directory_path (required): Path to the directory to scan.
  - pattern: Glob pattern for filtering files (default '*').
  - recursive: bool — if True, search subdirectories recursively (default False).
"""
import base64
import mimetypes
import structlog
from pathlib import Path

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — imported for consistency

log = structlog.get_logger(__name__)


@register_node("read_binary_files.read_all")
async def read_binary_files_read_all(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Read all binary files in a directory matching a glob pattern.

    Params:
      - directory_path (required): Path to the directory to scan.
      - pattern: Glob pattern to filter files (default '*'). Examples:
        '*.png', '**/*.pdf', 'data_*.csv'.
      - recursive: bool — search subdirectories when True (default False).
        When True, prepend '**/' to pattern automatically if not already present,
        or pass an explicitly recursive pattern like '**/*.png'.

    Returns:
      - files: List of file dicts, each containing:
        - name: Bare file name.
        - path: Full resolved path.
        - content_base64: Base64-encoded file content.
        - size: File size in bytes.
        - mime_type: Detected MIME type.
    """
    directory_path = config.get("directory_path") or input_data.get("directory_path")
    if not directory_path:
        raise ValueError("read_binary_files.read_all requires 'directory_path'")

    directory = Path(directory_path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory_path}")

    pattern = config.get("pattern") or input_data.get("pattern", "*")

    recursive_raw = config.get("recursive")
    if recursive_raw is None:
        recursive_raw = input_data.get("recursive", False)
    recursive = bool(recursive_raw)

    # If recursive is requested and the pattern doesn't already use **, prepend **/
    if recursive and not pattern.startswith("**/"):
        glob_pattern = f"**/{pattern}"
    else:
        glob_pattern = pattern

    matched_paths = list(directory.glob(glob_pattern))
    # Only include actual files, not directories
    file_paths = [p for p in matched_paths if p.is_file()]
    # Sort for deterministic ordering
    file_paths.sort()

    files: list[dict] = []
    for fp in file_paths:
        raw = fp.read_bytes()
        size = len(raw)
        content_base64 = base64.b64encode(raw).decode("utf-8")
        mime_type, _ = mimetypes.guess_type(str(fp))
        if not mime_type:
            mime_type = "application/octet-stream"
        files.append({
            "name": fp.name,
            "path": str(fp.resolve()),
            "content_base64": content_base64,
            "size": size,
            "mime_type": mime_type,
        })

    log.info(
        "read_binary_files.read_all",
        directory=str(directory),
        pattern=glob_pattern,
        count=len(files),
    )
    return {"files": files}
