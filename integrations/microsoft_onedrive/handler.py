"""Microsoft OneDrive integration — files and folders via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("onedrive.list_files")
async def onedrive_list_files(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List files and folders in a OneDrive directory.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      folder_path  — folder path relative to root, e.g. "Documents/Reports" (optional, default root)
      top          — maximum number of items to return (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    folder_path = merged.get("folder_path", "")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]

    if folder_path:
        endpoint = f"/me/drive/root:/{folder_path}:/children"
    else:
        endpoint = "/me/drive/root/children"

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(endpoint, headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    files = data.get("value", [])
    log.info("onedrive.list_files", folder_path=folder_path or "/", count=len(files))
    return {"files": files, "count": len(files)}


@register_node("onedrive.upload_file")
async def onedrive_upload_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Upload a file to OneDrive.

    config/input_data:
      access_token  — Microsoft Graph OAuth2 bearer token (required)
      file_path     — destination path in OneDrive, e.g. "Documents/report.pdf" (required)
      content       — file content as bytes or string (required)
      content_type  — MIME type of the file, e.g. "application/pdf" (optional)
      conflict      — conflict behavior: "rename", "replace", or "fail" (optional, default "replace")
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    file_path = merged.get("file_path")
    content = merged.get("content")
    if not file_path:
        raise ValueError("file_path is required for onedrive.upload_file")
    if content is None:
        raise ValueError("content is required for onedrive.upload_file")

    content_type = merged.get("content_type", "application/octet-stream")
    conflict = merged.get("conflict", "replace")
    if isinstance(content, str):
        content = content.encode("utf-8")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": content_type,
    }
    params = {"@microsoft.graph.conflictBehavior": conflict}

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=60) as client:
        r = await client.put(
            f"/me/drive/root:/{file_path}:/content",
            headers=headers,
            content=content,
            params=params,
        )
        r.raise_for_status()
        item = r.json()

    log.info("onedrive.upload_file", file_path=file_path, item_id=item.get("id"))
    return {"item": item, "item_id": item.get("id"), "file_path": file_path}


@register_node("onedrive.download_file")
async def onedrive_download_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Download a file from OneDrive by item ID or path.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      item_id      — OneDrive item ID (use this or file_path)
      file_path    — file path relative to root, e.g. "Documents/report.pdf" (use this or item_id)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    item_id = merged.get("item_id")
    file_path = merged.get("file_path")
    if not item_id and not file_path:
        raise ValueError("item_id or file_path is required for onedrive.download_file")

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    if item_id:
        endpoint = f"/me/drive/items/{item_id}/content"
    else:
        endpoint = f"/me/drive/root:/{file_path}:/content"

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=60) as client:
        r = await client.get(endpoint, headers=auth_headers, follow_redirects=True)
        r.raise_for_status()
        content = r.content

    log.info("onedrive.download_file", item_id=item_id, file_path=file_path, size=len(content))
    return {
        "content": content.decode("utf-8", errors="replace"),
        "content_bytes": list(content),
        "size": len(content),
    }


@register_node("onedrive.delete_file")
async def onedrive_delete_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a file or folder from OneDrive.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      item_id      — OneDrive item ID to delete (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    item_id = merged.get("item_id")
    if not item_id:
        raise ValueError("item_id is required for onedrive.delete_file")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.delete(f"/me/drive/items/{item_id}", headers=_graph_headers(access_token))
        r.raise_for_status()

    log.info("onedrive.delete_file", item_id=item_id)
    return {"deleted": True, "item_id": item_id}


@register_node("onedrive.create_folder")
async def onedrive_create_folder(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new folder in OneDrive.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      folder_name  — name of the new folder (required)
      parent_path  — parent folder path, e.g. "Documents" (optional, default root)
      conflict     — conflict behavior: "rename", "replace", or "fail" (optional, default "rename")
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    folder_name = merged.get("folder_name")
    parent_path = merged.get("parent_path", "")
    conflict = merged.get("conflict", "rename")
    if not folder_name:
        raise ValueError("folder_name is required for onedrive.create_folder")

    payload = {
        "name": folder_name,
        "folder": {},
        "@microsoft.graph.conflictBehavior": conflict,
    }

    if parent_path:
        endpoint = f"/me/drive/root:/{parent_path}:/children"
    else:
        endpoint = "/me/drive/root/children"

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post(endpoint, headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        folder = r.json()

    log.info("onedrive.create_folder", folder_name=folder_name, item_id=folder.get("id"))
    return {"folder": folder, "item_id": folder.get("id"), "folder_name": folder_name}
