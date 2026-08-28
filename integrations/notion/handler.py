"""Notion integration — databases, pages, blocks + polling."""
import structlog
import httpx

from core.execution_engine import register_node
from triggers.engine import register_poller
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)

NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


async def _notion(credential_id: str, db) -> httpx.AsyncClient:
    token = await get_access_token(credential_id, db)
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        timeout=30,
    )


@register_node("notion.query_database")
async def notion_query_db(config: dict, input_data: dict, credential_id: str, db) -> dict:
    database_id = config.get("database_id") or input_data.get("database_id")
    filter_ = config.get("filter") or input_data.get("filter")
    sorts = config.get("sorts") or input_data.get("sorts", [])
    page_size = config.get("page_size", 100)

    body = {"page_size": page_size}
    if filter_:
        body["filter"] = filter_
    if sorts:
        body["sorts"] = sorts

    async with await _notion(credential_id, db) as client:
        r = await client.post(f"{NOTION_BASE}/databases/{database_id}/query", json=body)
        r.raise_for_status()
        data = r.json()

    return {"results": data.get("results", []), "has_more": data.get("has_more")}


@register_node("notion.create_page")
async def notion_create_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    parent_id = config.get("parent_id") or input_data.get("parent_id")
    parent_type = config.get("parent_type", "database_id")  # database_id or page_id
    properties = config.get("properties") or input_data.get("properties", {})
    children = config.get("children") or input_data.get("children", [])
    icon = config.get("icon") or input_data.get("icon")
    cover = config.get("cover") or input_data.get("cover")

    body = {
        "parent": {parent_type: parent_id},
        "properties": properties,
        "children": children,
    }
    if icon:
        body["icon"] = icon
    if cover:
        body["cover"] = cover

    async with await _notion(credential_id, db) as client:
        r = await client.post(f"{NOTION_BASE}/pages", json=body)
        r.raise_for_status()
        data = r.json()
    return {"page_id": data["id"], "url": data.get("url")}


@register_node("notion.update_page")
async def notion_update_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    page_id = config.get("page_id") or input_data.get("page_id")
    properties = config.get("properties") or input_data.get("properties", {})
    archived = config.get("archived")

    body = {"properties": properties}
    if archived is not None:
        body["archived"] = archived

    async with await _notion(credential_id, db) as client:
        r = await client.patch(f"{NOTION_BASE}/pages/{page_id}", json=body)
        r.raise_for_status()
        data = r.json()
    return {"page_id": data["id"], "url": data.get("url")}


@register_node("notion.get_page")
async def notion_get_page(config: dict, input_data: dict, credential_id: str, db) -> dict:
    page_id = config.get("page_id") or input_data.get("page_id")

    async with await _notion(credential_id, db) as client:
        r = await client.get(f"{NOTION_BASE}/pages/{page_id}")
        r.raise_for_status()
        data = r.json()
    return data


@register_node("notion.append_blocks")
async def notion_append_blocks(config: dict, input_data: dict, credential_id: str, db) -> dict:
    block_id = config.get("block_id") or input_data.get("block_id")
    children = config.get("children") or input_data.get("children", [])

    async with await _notion(credential_id, db) as client:
        r = await client.patch(f"{NOTION_BASE}/blocks/{block_id}/children",
                               json={"children": children})
        r.raise_for_status()
        data = r.json()
    return {"results": data.get("results", [])}


@register_node("notion.search")
async def notion_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    query = config.get("query") or input_data.get("query", "")
    filter_ = config.get("filter")
    sort = config.get("sort", {"direction": "descending", "timestamp": "last_edited_time"})

    body = {"query": query, "sort": sort}
    if filter_:
        body["filter"] = filter_

    async with await _notion(credential_id, db) as client:
        r = await client.post(f"{NOTION_BASE}/search", json=body)
        r.raise_for_status()
        data = r.json()
    return {"results": data.get("results", []), "has_more": data.get("has_more")}


@register_node("notion.list_databases")
async def notion_list_databases(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _notion(credential_id, db) as client:
        r = await client.post(f"{NOTION_BASE}/search",
                              json={"filter": {"value": "database", "property": "object"}})
        r.raise_for_status()
        data = r.json()
    dbs = [{"id": d["id"], "title": _notion_title(d)} for d in data.get("results", [])]
    return {"databases": dbs}


def _notion_title(obj: dict) -> str:
    title_prop = obj.get("title", [])
    if title_prop:
        return title_prop[0].get("plain_text", "Untitled")
    props = obj.get("properties", {})
    title_key = next((k for k, v in props.items() if v.get("type") == "title"), None)
    if title_key:
        items = props[title_key].get("title", [])
        return items[0].get("plain_text", "Untitled") if items else "Untitled"
    return "Untitled"


# ─── Polling: new database row ────────────────────────────────────────────────

_notion_seen: dict[str, set] = {}


@register_poller("notion", "new_row")
async def poll_notion_new_row(config: dict, credential_id: str, db) -> list[dict]:
    database_id = config.get("database_id")
    key = f"{credential_id}:{database_id}"
    if key not in _notion_seen:
        _notion_seen[key] = set()

    try:
        async with await _notion(credential_id, db) as client:
            r = await client.post(
                f"{NOTION_BASE}/databases/{database_id}/query",
                json={"page_size": 20, "sorts": [{"timestamp": "created_time", "direction": "descending"}]},
            )
            r.raise_for_status()
            data = r.json()

        new_items = []
        for page in data.get("results", []):
            if page["id"] not in _notion_seen[key]:
                new_items.append(page)
                _notion_seen[key].add(page["id"])
        return new_items
    except Exception as e:
        log.error("notion_poll_error", error=str(e))
        return []
