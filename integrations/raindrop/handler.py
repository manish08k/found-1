"""
Raindrop.io bookmark manager integration.

Provides bookmark (raindrop) listing, creation, updating, and
collection listing via the Raindrop.io REST API v1.

Credential fields:
  - access_token : Raindrop.io OAuth access token or test token
    (found in Integration settings > For Developers > Create test token).

Auth: Bearer token via Authorization header.
Base URL: https://api.raindrop.io/rest/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.raindrop.io/rest/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Raindrop credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Raindrop API error {r.status_code}: {detail}")


@register_node("raindrop.list_bookmarks")
async def raindrop_list_bookmarks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List bookmarks (raindrops) from a collection.

    Params:
      - collection_id: Numeric collection ID. Use 0 for all, -1 for unsorted,
        -99 for trash (default 0).
      - search: Search query string.
      - sort: Sort field — 'score' (relevance), '-created' (newest), 'created' (oldest),
        '-sort' (custom), 'title', '-title', 'domain', '-domain' (default '-created').
      - page: Page number starting at 0 (default 0).
      - per_page: Results per page, max 50 (default 25).
      - tags: Comma-separated list of tags to filter by.
    """
    collection_id = config.get("collection_id") or input_data.get("collection_id", 0)
    params: dict = {}

    search = config.get("search") or input_data.get("search")
    if search:
        params["search"] = search

    sort = config.get("sort") or input_data.get("sort", "-created")
    params["sort"] = sort

    page = int(config.get("page") or input_data.get("page", 0))
    params["page"] = page

    per_page = min(int(config.get("per_page") or input_data.get("per_page", 25)), 50)
    params["perpage"] = per_page

    tags_raw = config.get("tags") or input_data.get("tags")
    if tags_raw:
        tags = tags_raw if isinstance(tags_raw, list) else [t.strip() for t in str(tags_raw).split(",") if t.strip()]
        params["search"] = (params.get("search", "") + " " + " ".join(f"#{t}" for t in tags)).strip()

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/raindrops/{collection_id}", params=params)
        _raise_for_status(r)
        data = r.json()

    bookmarks = data.get("items", [])
    log.info("raindrop.list_bookmarks", collection_id=collection_id, count=len(bookmarks))
    return {
        "bookmarks": bookmarks,
        "count": data.get("count"),
        "collectionId": collection_id,
    }


@register_node("raindrop.create_bookmark")
async def raindrop_create_bookmark(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a new bookmark (raindrop).

    Params:
      - link (required): URL to bookmark.
      - title: Title of the bookmark. If omitted, Raindrop will fetch the page title.
      - excerpt: Short description / excerpt.
      - collection_id: Numeric collection ID to save into (default: unsorted).
      - tags: List or comma-separated string of tags.
      - important: bool — mark as favourite.
      - cover: URL of a cover image.
      - type: Bookmark type — 'link', 'article', 'image', 'video', 'document',
        'audio' (default 'link').
    """
    link = config.get("link") or input_data.get("link")
    if not link:
        raise ValueError("raindrop.create_bookmark requires 'link'")

    payload: dict = {"link": link, "pleaseParse": {}}

    title = config.get("title") or input_data.get("title")
    if title:
        payload["title"] = title

    excerpt = config.get("excerpt") or input_data.get("excerpt")
    if excerpt:
        payload["excerpt"] = excerpt

    collection_id = config.get("collection_id") or input_data.get("collection_id")
    if collection_id is not None:
        payload["collection"] = {"$id": int(collection_id)}

    tags_raw = config.get("tags") or input_data.get("tags")
    if tags_raw:
        payload["tags"] = tags_raw if isinstance(tags_raw, list) else [t.strip() for t in str(tags_raw).split(",") if t.strip()]

    important = config.get("important")
    if important is None:
        important = input_data.get("important")
    if important is not None:
        payload["important"] = bool(important)

    cover = config.get("cover") or input_data.get("cover")
    if cover:
        payload["cover"] = cover

    btype = config.get("type") or input_data.get("type", "link")
    payload["type"] = btype

    async with await _client(credential_id, db) as client:
        r = await client.post("/raindrop", json=payload)
        _raise_for_status(r)
        data = r.json()

    bookmark = data.get("item", data)
    log.info("raindrop.create_bookmark", link=link, id=bookmark.get("_id"))
    return {"bookmark": bookmark, "id": bookmark.get("_id")}


@register_node("raindrop.update_bookmark")
async def raindrop_update_bookmark(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update an existing bookmark (raindrop) by ID.

    Params:
      - raindrop_id (required): Numeric ID of the raindrop to update.
      - title: New title.
      - excerpt: New description/excerpt.
      - link: New URL.
      - collection_id: Move to a different collection by ID.
      - tags: List or comma-separated string of tags (replaces existing).
      - important: bool — mark/unmark as favourite.
      - cover: New cover image URL.
    """
    raindrop_id = config.get("raindrop_id") or input_data.get("raindrop_id")
    if not raindrop_id:
        raise ValueError("raindrop.update_bookmark requires 'raindrop_id'")

    payload: dict = {}

    title = config.get("title") or input_data.get("title")
    if title:
        payload["title"] = title

    excerpt = config.get("excerpt") or input_data.get("excerpt")
    if excerpt:
        payload["excerpt"] = excerpt

    link = config.get("link") or input_data.get("link")
    if link:
        payload["link"] = link

    collection_id = config.get("collection_id") or input_data.get("collection_id")
    if collection_id is not None:
        payload["collection"] = {"$id": int(collection_id)}

    tags_raw = config.get("tags") or input_data.get("tags")
    if tags_raw is not None:
        payload["tags"] = tags_raw if isinstance(tags_raw, list) else [t.strip() for t in str(tags_raw).split(",") if t.strip()]

    important = config.get("important")
    if important is None:
        important = input_data.get("important")
    if important is not None:
        payload["important"] = bool(important)

    cover = config.get("cover") or input_data.get("cover")
    if cover:
        payload["cover"] = cover

    if not payload:
        raise ValueError("raindrop.update_bookmark requires at least one field to update")

    async with await _client(credential_id, db) as client:
        r = await client.put(f"/raindrop/{raindrop_id}", json=payload)
        _raise_for_status(r)
        data = r.json()

    bookmark = data.get("item", data)
    log.info("raindrop.update_bookmark", raindrop_id=raindrop_id)
    return {"bookmark": bookmark, "id": bookmark.get("_id")}


@register_node("raindrop.list_collections")
async def raindrop_list_collections(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all root collections in the Raindrop account.

    Params:
      - include_children: bool — also fetch child (nested) collections (default False).
    """
    async with await _client(credential_id, db) as client:
        r = await client.get("/collections")
        _raise_for_status(r)
        data = r.json()

    collections = data.get("items", [])

    include_children = config.get("include_children") or input_data.get("include_children", False)
    children: list = []
    if include_children:
        async with await _client(credential_id, db) as client:
            rc = await client.get("/collections/childrens")
            if rc.status_code < 300:
                children = rc.json().get("items", [])

    log.info("raindrop.list_collections", count=len(collections), children=len(children))
    return {
        "collections": collections,
        "children": children,
        "count": len(collections),
    }
