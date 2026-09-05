"""
LocalFileTrigger integration.

Watches a local filesystem directory for changes and returns file info/events.
Uses stdlib os.path and os.stat — no external HTTP client required.

Credential fields:
  - directory_path : Absolute path to the directory to watch
"""
import os
import os.path
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _stat_to_dict(path: str, stat_result) -> dict:
    """Convert an os.stat_result to a serialisable dictionary."""
    return {
        "path": path,
        "name": os.path.basename(path),
        "size_bytes": stat_result.st_size,
        "is_file": os.path.isfile(path),
        "is_dir": os.path.isdir(path),
        "modified_time": stat_result.st_mtime,
        "created_time": stat_result.st_ctime,
        "accessed_time": stat_result.st_atime,
    }


@register_node("local_file_trigger.watch_directory")
async def local_file_trigger_watch_directory(
    config: dict, input_data: dict, credential_id: str, db
) -> dict:
    """
    Scan a directory and return information about its contents.

    Returns a snapshot of files and directories. Poll repeatedly to detect changes.
    Compares against a provided 'previous_snapshot' to surface added/removed/modified entries.
    """
    creds = await get_credential_data(credential_id, db)
    directory_path = (
        config.get("directory_path")
        or input_data.get("directory_path")
        or creds.get("directory_path")
    )
    recursive = bool(config.get("recursive") or input_data.get("recursive", False))
    previous_snapshot: dict = config.get("previous_snapshot") or input_data.get("previous_snapshot", {})

    if not directory_path:
        raise ValueError("local_file_trigger.watch_directory requires 'directory_path'")
    if not os.path.isdir(directory_path):
        raise ValueError(f"Directory does not exist or is not a directory: {directory_path}")

    log.info("local_file_trigger.watch_directory", directory=directory_path, recursive=recursive)

    current_snapshot: dict = {}

    if recursive:
        for root, dirs, files in os.walk(directory_path):
            for name in files + dirs:
                full_path = os.path.join(root, name)
                try:
                    stat = os.stat(full_path)
                    current_snapshot[full_path] = stat.st_mtime
                except OSError:
                    pass
    else:
        try:
            entries = os.listdir(directory_path)
        except OSError as exc:
            raise ValueError(f"Cannot list directory '{directory_path}': {exc}") from exc
        for name in entries:
            full_path = os.path.join(directory_path, name)
            try:
                stat = os.stat(full_path)
                current_snapshot[full_path] = stat.st_mtime
            except OSError:
                pass

    # Compute diff against previous snapshot
    added = [p for p in current_snapshot if p not in previous_snapshot]
    removed = [p for p in previous_snapshot if p not in current_snapshot]
    modified = [
        p for p in current_snapshot
        if p in previous_snapshot and current_snapshot[p] != previous_snapshot[p]
    ]

    events = []
    for path in added:
        events.append({"event": "added", "path": path})
    for path in removed:
        events.append({"event": "removed", "path": path})
    for path in modified:
        events.append({"event": "modified", "path": path})

    return {
        "directory": directory_path,
        "file_count": len(current_snapshot),
        "events": events,
        "added": added,
        "removed": removed,
        "modified": modified,
        "snapshot": current_snapshot,
    }


@register_node("local_file_trigger.get_file_info")
async def local_file_trigger_get_file_info(
    config: dict, input_data: dict, credential_id: str, db
) -> dict:
    """Get detailed stat information for a file or directory path."""
    file_path = config.get("file_path") or input_data.get("file_path")

    if not file_path:
        raise ValueError("local_file_trigger.get_file_info requires 'file_path'")
    if not os.path.exists(file_path):
        return {"found": False, "path": file_path}

    try:
        stat = os.stat(file_path)
    except OSError as exc:
        raise ValueError(f"Cannot stat path '{file_path}': {exc}") from exc

    log.info("local_file_trigger.get_file_info", path=file_path)

    info = _stat_to_dict(file_path, stat)
    info["found"] = True
    info["extension"] = os.path.splitext(file_path)[1]
    info["absolute_path"] = os.path.abspath(file_path)

    if os.path.isdir(file_path):
        try:
            info["children"] = os.listdir(file_path)
            info["child_count"] = len(info["children"])
        except OSError:
            info["children"] = []
            info["child_count"] = 0

    return info
