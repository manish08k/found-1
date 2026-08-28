"""
Dropbox integration — files, folders, sharing, search.
Nodes: dropbox.list_folder, dropbox.get_metadata, dropbox.download_file,
       dropbox.upload_file, dropbox.create_folder, dropbox.delete,
       dropbox.search, dropbox.create_shared_link
"""
import base64
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

DROPBOX_API = "https://api.dropboxapi.com/2"
DROPBOX_CONTENT = "https://content.dropboxapi.com/2"


def _headers(config, json_content=True):
    token = config.get("access_token") or getattr(settings, "DROPBOX_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("dropbox nodes require DROPBOX_ACCESS_TOKEN or 'access_token'")
    h = {"Authorization": f"Bearer {token}"}
    if json_content:
        h["Content-Type"] = "application/json"
    return h


@register_node("dropbox.list_folder")
async def dropbox_list_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    path = merged.get("path", "")  # empty string = root

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DROPBOX_API}/files/list_folder",
            json={"path": path, "recursive": merged.get("recursive", False)},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()

    entries = [{"name": e["name"], "path": e["path_lower"], "type": e[".tag"], "size": e.get("size")}
               for e in data.get("entries", [])]
    return {"entries": entries, "count": len(entries), "has_more": data.get("has_more", False)}


@register_node("dropbox.get_metadata")
async def dropbox_get_metadata(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    path = merged.get("path")
    if not path:
        raise ValueError("dropbox.get_metadata requires 'path'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DROPBOX_API}/files/get_metadata",
            json={"path": path},
            headers=_headers(merged),
        )
        r.raise_for_status()
        return {"metadata": r.json()}


@register_node("dropbox.download_file")
async def dropbox_download_file(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    path = merged.get("path")
    if not path:
        raise ValueError("dropbox.download_file requires 'path'")

    headers = {
        "Authorization": f"Bearer {merged.get('access_token') or getattr(settings, 'DROPBOX_ACCESS_TOKEN', '')}",
        "Dropbox-API-Arg": f'{{"path": "{path}"}}',
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{DROPBOX_CONTENT}/files/download", headers=headers)
        r.raise_for_status()
        content_b64 = base64.b64encode(r.content).decode()

    return {"content_base64": content_b64, "size": len(r.content), "path": path}


@register_node("dropbox.create_folder")
async def dropbox_create_folder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    path = merged.get("path")
    if not path:
        raise ValueError("dropbox.create_folder requires 'path'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DROPBOX_API}/files/create_folder_v2",
            json={"path": path, "autorename": merged.get("autorename", False)},
            headers=_headers(merged),
        )
        r.raise_for_status()
        return {"folder": r.json().get("metadata"), "ok": True}


@register_node("dropbox.delete")
async def dropbox_delete(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    path = merged.get("path")
    if not path:
        raise ValueError("dropbox.delete requires 'path'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DROPBOX_API}/files/delete_v2",
            json={"path": path},
            headers=_headers(merged),
        )
        r.raise_for_status()
        return {"deleted": r.json().get("metadata", {}).get("path_lower"), "ok": True}


@register_node("dropbox.search")
async def dropbox_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    query = merged.get("query")
    if not query:
        raise ValueError("dropbox.search requires 'query'")

    path = merged.get("path", "")
    max_results = min(int(merged.get("max_results", 20)), 100)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DROPBOX_API}/files/search_v2",
            json={"query": query, "options": {"path": path, "max_results": max_results}},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()

    matches = [m["metadata"]["metadata"] for m in data.get("matches", []) if "metadata" in m.get("metadata", {})]
    results = [{"name": m.get("name"), "path": m.get("path_lower"), "type": m.get(".tag")} for m in matches]
    return {"results": results, "count": len(results)}


@register_node("dropbox.create_shared_link")
async def dropbox_create_shared_link(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    path = merged.get("path")
    if not path:
        raise ValueError("dropbox.create_shared_link requires 'path'")

    async with httpx.AsyncClient(timeout=30) as client:
        # Try to create; if already exists, retrieve existing
        r = await client.post(
            f"{DROPBOX_API}/sharing/create_shared_link_with_settings",
            json={"path": path, "settings": {"requested_visibility": merged.get("visibility", "public")}},
            headers=_headers(merged),
        )
        if r.status_code == 409:
            # Link already exists
            r2 = await client.post(
                f"{DROPBOX_API}/sharing/list_shared_links",
                json={"path": path, "direct_only": True},
                headers=_headers(merged),
            )
            r2.raise_for_status()
            links = r2.json().get("links", [])
            return {"url": links[0]["url"] if links else None, "already_existed": True}
        r.raise_for_status()
        data = r.json()

    return {"url": data.get("url"), "ok": True}
