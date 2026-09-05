"""RenameKeys integration — rename fields in a dictionary.

No credentials required.

Nodes:
  - rename_keys.rename : rename keys in the input dict according to a
                         list of {from, to} mappings.

Config:
  - mappings : list of objects with 'from' and 'to' string fields
                e.g. [{"from": "old_name", "to": "new_name"}, ...]
  - keep_unmapped : bool (default True) — keep keys not listed in mappings
"""
import structlog
import httpx  # noqa: F401 — standard import

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)


@register_node("rename_keys.rename")
async def rename(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Rename keys in input_data according to config['mappings']."""
    mappings = config.get("mappings", [])
    keep_unmapped = config.get("keep_unmapped", True)

    if not isinstance(mappings, list):
        raise ValueError("'mappings' must be a list of {from, to} objects")

    # Build rename map: old_key -> new_key
    rename_map: dict[str, str] = {}
    for entry in mappings:
        src = entry.get("from")
        dst = entry.get("to")
        if not src or not dst:
            raise ValueError(
                f"Each mapping must have 'from' and 'to' fields, got: {entry}"
            )
        rename_map[src] = dst

    log.info("rename_keys.rename", mapping_count=len(rename_map))

    result: dict = {}
    renamed: list[str] = []
    skipped: list[str] = []

    for key, value in input_data.items():
        if key in rename_map:
            new_key = rename_map[key]
            result[new_key] = value
            renamed.append(f"{key} -> {new_key}")
        else:
            if keep_unmapped:
                result[key] = value
            else:
                skipped.append(key)

    log.info("rename_keys.rename.done", renamed=len(renamed), skipped=len(skipped))
    return {
        "data": result,
        "renamed": renamed,
        "skipped": skipped,
    }
