"""
Box integration — files, folders, uploads, downloads.
Nodes: box.list_folder, box.get_file_info, box.download_file,
       box.upload_file, box.create_folder, box.delete_item,
       box.search, box.share_link
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

BOX_API = "https://api.box.com/2.0"
BOX_UPLOAD = "https://upload.box.com/api/2.0"


async def _box_token(config: dict) -> str:
    """Get Box API token via OAuth2 client credentials or use stored token."""
    # Prefer a pre-set access token (e.g. developer token for testing)
    token = config.get("access_token") or getattr(settings, "BOX_ACCESS_TOKEN", "")
    if token:
        return token

    client_id = config.get("client_id") or getattr(settings, "BOX_CLIENT_ID", "")
    client_secret = config.get("client_secret") or getattr(settings, "BOX_CLIENT_SECRET", "")
    enterprise_id = config.get("enterprise_id") or getattr(settings, "BOX_ENTERPRISE_ID", "")

    if not all([client_id, client_secret, enterprise_id]):
        raise ValueError("box nodes require BOX_ACCESS_TOKEN or (BOX_CLIENT_ID, BOX_CLIENT_SECRET, BOX_ENTERPRISE_ID)")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.box.com/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "box_subject_type": "enterprise",
                "box_subject_id": enterprise_id,
            },
        )
        r.raise_for_status()
        return r.json()["access_token"]


@register_node("box.list_folder")
async def box_list_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _box_token(merged)
    folder_id = merged.get("folder_id", "0")  # "0" = root
    limit = min(int(merged.get("limit", 100)), 1000)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BOX_API}/folders/{folder_id}/items",
            params={"limit": limit, "fields": "id,name,type,size,modified_at"},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    entries = [{"id": e["id"], "name": e["name"], "type": e["type"],
                "size": e.get("size"), "modified_at": e.get("modified_at")}
               for e in data.get("entries", [])]
    return {"entries": entries, "total_count": data.get("total_count", len(entries)), "folder_id": folder_id}


@register_node("box.get_file_info")
async def box_get_file_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _box_token(merged)
    file_id = merged.get("file_id")
    if not file_id:
        raise ValueError("box.get_file_info requires 'file_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BOX_API}/files/{file_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        return {"file": r.json()}


@register_node("box.download_file")
async def box_download_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Download file content as base64-encoded string."""
    import base64
    merged = {**config, **input_data}
    token = await _box_token(merged)
    file_id = merged.get("file_id")
    if not file_id:
        raise ValueError("box.download_file requires 'file_id'")

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        r = await client.get(
            f"{BOX_API}/files/{file_id}/content",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        content_b64 = base64.b64encode(r.content).decode()

    return {"content_base64": content_b64, "size": len(r.content), "file_id": file_id}


@register_node("box.create_folder")
async def box_create_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _box_token(merged)
    name = merged.get("name", "New Folder")
    parent_id = merged.get("parent_id", "0")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BOX_API}/folders",
            json={"name": name, "parent": {"id": parent_id}},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    return {"id": data["id"], "name": data["name"], "ok": True}


@register_node("box.delete_item")
async def box_delete_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _box_token(merged)
    item_id = merged.get("item_id")
    item_type = merged.get("item_type", "file")  # file | folder
    if not item_id:
        raise ValueError("box.delete_item requires 'item_id'")

    path = f"{item_type}s/{item_id}"
    params = {}
    if item_type == "folder":
        params["recursive"] = "true"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(
            f"{BOX_API}/{path}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()

    return {"ok": True, "deleted": item_id}


@register_node("box.search")
async def box_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _box_token(merged)
    query = merged.get("query")
    if not query:
        raise ValueError("box.search requires 'query'")

    limit = min(int(merged.get("limit", 20)), 200)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BOX_API}/search",
            params={"query": query, "limit": limit, "fields": "id,name,type,size"},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    entries = [{"id": e["id"], "name": e["name"], "type": e["type"]} for e in data.get("entries", [])]
    return {"entries": entries, "total_count": data.get("total_count", len(entries))}


@register_node("box.share_link")
async def box_share_link(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _box_token(merged)
    file_id = merged.get("file_id")
    item_type = merged.get("item_type", "file")  # file | folder
    access_level = merged.get("access", "open")  # open | company | collaborators

    if not file_id:
        raise ValueError("box.share_link requires 'file_id' (or folder_id)")

    path = f"{item_type}s/{file_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(
            f"{BOX_API}/{path}",
            json={"shared_link": {"access": access_level}},
            params={"fields": "shared_link"},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    link = data.get("shared_link", {})
    return {"url": link.get("url"), "download_url": link.get("download_url"), "access": link.get("access")}
