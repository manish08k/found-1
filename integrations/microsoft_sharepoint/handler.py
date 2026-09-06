"""Microsoft SharePoint integration — sites and lists via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("sharepoint.list_sites")
async def sharepoint_list_sites(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List SharePoint sites accessible to the authenticated user.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      top          — maximum number of sites to return (optional)
      search       — search keyword to filter sites by (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("search"):
        params["search"] = merged["search"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/sites", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    sites = data.get("value", [])
    log.info("sharepoint.list_sites", count=len(sites))
    return {"sites": sites, "count": len(sites)}


@register_node("sharepoint.list_lists")
async def sharepoint_list_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List SharePoint lists in a site.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      site_id      — SharePoint site ID (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    site_id = merged.get("site_id")
    if not site_id:
        raise ValueError("site_id is required for sharepoint.list_lists")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/sites/{site_id}/lists", headers=_graph_headers(access_token))
        r.raise_for_status()
        data = r.json()

    lists = data.get("value", [])
    log.info("sharepoint.list_lists", site_id=site_id, count=len(lists))
    return {"lists": lists, "count": len(lists)}


@register_node("sharepoint.create_list_item")
async def sharepoint_create_list_item(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new item in a SharePoint list.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      site_id      — SharePoint site ID (required)
      list_id      — SharePoint list ID (required)
      fields       — dict of field name/value pairs for the new item (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    site_id = merged.get("site_id")
    list_id = merged.get("list_id")
    fields = merged.get("fields")
    if not site_id:
        raise ValueError("site_id is required for sharepoint.create_list_item")
    if not list_id:
        raise ValueError("list_id is required for sharepoint.create_list_item")
    if not fields:
        raise ValueError("fields is required for sharepoint.create_list_item")

    payload = {"fields": fields}

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post(
            f"/sites/{site_id}/lists/{list_id}/items",
            headers=_graph_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        item = r.json()

    log.info("sharepoint.create_list_item", site_id=site_id, list_id=list_id, item_id=item.get("id"))
    return {"item": item, "item_id": item.get("id")}


@register_node("sharepoint.get_list_items")
async def sharepoint_get_list_items(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get items from a SharePoint list.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      site_id      — SharePoint site ID (required)
      list_id      — SharePoint list ID (required)
      top          — maximum number of items to return (optional)
      filter       — OData filter expression (optional)
      expand       — OData expand expression, e.g. "fields" (optional, default "fields")
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    site_id = merged.get("site_id")
    list_id = merged.get("list_id")
    if not site_id:
        raise ValueError("site_id is required for sharepoint.get_list_items")
    if not list_id:
        raise ValueError("list_id is required for sharepoint.get_list_items")

    params: dict = {"$expand": merged.get("expand", "fields")}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/sites/{site_id}/lists/{list_id}/items",
            headers=_graph_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("value", [])
    log.info("sharepoint.get_list_items", site_id=site_id, list_id=list_id, count=len(items))
    return {"items": items, "count": len(items)}


@register_node("sharepoint.update_list_item")
async def sharepoint_update_list_item(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing item in a SharePoint list.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      site_id      — SharePoint site ID (required)
      list_id      — SharePoint list ID (required)
      item_id      — item ID to update (required)
      fields       — dict of field name/value pairs to update (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    site_id = merged.get("site_id")
    list_id = merged.get("list_id")
    item_id = merged.get("item_id")
    fields = merged.get("fields")
    if not site_id:
        raise ValueError("site_id is required for sharepoint.update_list_item")
    if not list_id:
        raise ValueError("list_id is required for sharepoint.update_list_item")
    if not item_id:
        raise ValueError("item_id is required for sharepoint.update_list_item")
    if not fields:
        raise ValueError("fields is required for sharepoint.update_list_item")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.patch(
            f"/sites/{site_id}/lists/{list_id}/items/{item_id}/fields",
            headers=_graph_headers(access_token),
            json=fields,
        )
        r.raise_for_status()
        updated_fields = r.json()

    log.info("sharepoint.update_list_item", site_id=site_id, list_id=list_id, item_id=item_id)
    return {"fields": updated_fields, "item_id": item_id, "updated": True}


@register_node("sharepoint.delete_list_item")
async def sharepoint_delete_list_item(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an item from a SharePoint list.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      site_id      — SharePoint site ID (required)
      list_id      — SharePoint list ID (required)
      item_id      — item ID to delete (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    site_id = merged.get("site_id")
    list_id = merged.get("list_id")
    item_id = merged.get("item_id")
    if not site_id:
        raise ValueError("site_id is required for sharepoint.delete_list_item")
    if not list_id:
        raise ValueError("list_id is required for sharepoint.delete_list_item")
    if not item_id:
        raise ValueError("item_id is required for sharepoint.delete_list_item")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.delete(
            f"/sites/{site_id}/lists/{list_id}/items/{item_id}",
            headers=_graph_headers(access_token),
        )
        r.raise_for_status()

    log.info("sharepoint.delete_list_item", site_id=site_id, list_id=list_id, item_id=item_id)
    return {"deleted": True, "item_id": item_id}
