"""Google Drive (Activepieces integration) — handler for google_drive_ap integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://www.googleapis.com/drive/v3"


@register_node("google_drive_ap.list_files")
async def google_drive_ap_list_files(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List files.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/files", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("google_drive_ap.list_files")
    return {"data": data}

@register_node("google_drive_ap.get_file")
async def google_drive_ap_get_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get file metadata.

    config/input_data:
      api_key — API key or token (required)
      file_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    file_id = merged.get("file_id") or ""
    if not file_id:
        raise ValueError("file_id required for google_drive_ap.get_file")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/files/{file_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("google_drive_ap.get_file")
    return {"data": data}

@register_node("google_drive_ap.delete_file")
async def google_drive_ap_delete_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a file.

    config/input_data:
      api_key — API key or token (required)
      file_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    file_id = merged.get("file_id") or ""
    if not file_id:
        raise ValueError("file_id required for google_drive_ap.delete_file")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(f"{BASE_URL}/files/{file_id}", headers=headers)
        r.raise_for_status()
    log.info("google_drive_ap.delete_file")
    return {"ok": True}

@register_node("google_drive_ap.create_folder")
async def google_drive_ap_create_folder(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a folder.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    if not name:
        raise ValueError("name required for google_drive_ap.create_folder")
    payload = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/files", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("google_drive_ap.create_folder")
    return {"data": data}
