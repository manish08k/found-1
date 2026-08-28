"""
Confluence integration — spaces, pages, search, comments.
Nodes: confluence.get_page, confluence.create_page, confluence.update_page,
       confluence.search, confluence.get_space_pages, confluence.add_comment
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


def _headers_and_base(config):
    base_url = config.get("base_url") or getattr(settings, "CONFLUENCE_BASE_URL", "")
    email = config.get("email") or getattr(settings, "CONFLUENCE_EMAIL", "")
    api_token = config.get("api_token") or getattr(settings, "CONFLUENCE_API_TOKEN", "")

    if not base_url or not email or not api_token:
        raise ValueError("confluence nodes require base_url, email, api_token")

    base_url = base_url.rstrip("/")
    auth = (email, api_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    return base_url, auth, headers


@register_node("confluence.get_page")
async def confluence_get_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth, headers = _headers_and_base(merged)
    page_id = merged.get("page_id")
    if not page_id:
        raise ValueError("confluence.get_page requires 'page_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/wiki/rest/api/content/{page_id}",
            params={"expand": "body.storage,version,space"},
            auth=auth,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()

    body = data.get("body", {}).get("storage", {}).get("value", "")
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "body": body,
        "version": data.get("version", {}).get("number"),
        "space_key": data.get("space", {}).get("key"),
    }


@register_node("confluence.create_page")
async def confluence_create_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth, headers = _headers_and_base(merged)
    space_key = merged.get("space_key")
    title = merged.get("title", "New Page")
    body = merged.get("body", "")
    parent_id = merged.get("parent_id")

    if not space_key:
        raise ValueError("confluence.create_page requires 'space_key'")

    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/wiki/rest/api/content", json=payload, auth=auth, headers=headers)
        r.raise_for_status()
        data = r.json()

    return {"id": data.get("id"), "title": data.get("title"), "url": data.get("_links", {}).get("webui"), "ok": True}


@register_node("confluence.update_page")
async def confluence_update_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth, headers = _headers_and_base(merged)
    page_id = merged.get("page_id")
    if not page_id:
        raise ValueError("confluence.update_page requires 'page_id'")

    # Get current version first
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{base_url}/wiki/rest/api/content/{page_id}?expand=version", auth=auth, headers=headers)
        r.raise_for_status()
        current = r.json()
        current_version = current["version"]["number"]

        payload = {
            "version": {"number": current_version + 1},
            "title": merged.get("title") or current.get("title"),
            "type": "page",
            "body": {"storage": {"value": merged.get("body", ""), "representation": "storage"}},
        }

        r = await client.put(
            f"{base_url}/wiki/rest/api/content/{page_id}",
            json=payload,
            auth=auth,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()

    return {"id": data.get("id"), "version": data.get("version", {}).get("number"), "ok": True}


@register_node("confluence.search")
async def confluence_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth, headers = _headers_and_base(merged)
    query = merged.get("query") or merged.get("cql", "")
    if not query:
        raise ValueError("confluence.search requires 'query'")

    limit = min(int(merged.get("limit", 25)), 100)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/wiki/rest/api/search",
            params={"cql": f'text ~ "{query}"', "limit": limit},
            auth=auth,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()

    results = [
        {"id": r.get("content", {}).get("id"), "title": r.get("content", {}).get("title"),
         "type": r.get("resultGlobalContainer", {}).get("displayUrl"), "excerpt": r.get("excerpt")}
        for r in data.get("results", [])
    ]
    return {"results": results, "count": data.get("totalSize", len(results))}


@register_node("confluence.get_space_pages")
async def confluence_get_space_pages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    base_url, auth, headers = _headers_and_base(merged)
    space_key = merged.get("space_key")
    if not space_key:
        raise ValueError("confluence.get_space_pages requires 'space_key'")

    limit = min(int(merged.get("limit", 25)), 100)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/wiki/rest/api/content",
            params={"spaceKey": space_key, "type": "page", "limit": limit, "expand": "version"},
            auth=auth,
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()

    pages = [{"id": p.get("id"), "title": p.get("title"), "version": p.get("version", {}).get("number")}
             for p in data.get("results", [])]
    return {"pages": pages, "count": len(pages), "space_key": space_key}
