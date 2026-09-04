"""
Webflow integration.

Credential fields:
  - api_key: Webflow API key

Auth: Authorization: Bearer {api_key}
Base URL: https://api.webflow.com/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

WEBFLOW_BASE_URL = "https://api.webflow.com/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Webflow credential is missing 'api_key'")
    return httpx.AsyncClient(
        base_url=WEBFLOW_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Webflow API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by listing sites."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/sites")
    data = _check(r)
    sites = data.get("sites", [])
    return {"ok": True, "site_count": len(sites)}


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

@register_node("webflow.list_sites")
async def webflow_list_sites(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites — list all sites."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/sites")
    return _check(r)


@register_node("webflow.get_site")
async def webflow_get_site(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites/{site_id} — get a single site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("webflow.get_site requires 'site_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sites/{site_id}")
    return _check(r)


@register_node("webflow.publish_site")
async def webflow_publish_site(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /sites/{site_id}/publish — publish a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("webflow.publish_site requires 'site_id'")
    domains = config.get("domains") or input_data.get("domains", [])
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/sites/{site_id}/publish", json={"publishToWebflowSubdomain": True, "customDomains": domains})
    return _check(r)


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@register_node("webflow.list_collections")
async def webflow_list_collections(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites/{site_id}/collections — list CMS collections."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("webflow.list_collections requires 'site_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sites/{site_id}/collections")
    return _check(r)


@register_node("webflow.get_collection")
async def webflow_get_collection(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /collections/{collection_id} — get a single collection."""
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    if not collection_id:
        raise ValueError("webflow.get_collection requires 'collection_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/collections/{collection_id}")
    return _check(r)


# ---------------------------------------------------------------------------
# Collection Items
# ---------------------------------------------------------------------------

@register_node("webflow.list_collection_items")
async def webflow_list_collection_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /collections/{collection_id}/items — list items in a collection."""
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    if not collection_id:
        raise ValueError("webflow.list_collection_items requires 'collection_id'")
    params = {}
    for key in ("offset", "limit"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/collections/{collection_id}/items", params=params)
    return _check(r)


@register_node("webflow.get_collection_item")
async def webflow_get_collection_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /collections/{collection_id}/items/{item_id} — get a single collection item."""
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    item_id = config.get("item_id") or input_data.get("item_id")
    if not collection_id or not item_id:
        raise ValueError("webflow.get_collection_item requires 'collection_id' and 'item_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/collections/{collection_id}/items/{item_id}")
    return _check(r)


@register_node("webflow.create_collection_item")
async def webflow_create_collection_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /collections/{collection_id}/items — create a new collection item."""
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    if not collection_id:
        raise ValueError("webflow.create_collection_item requires 'collection_id'")
    field_data = config.get("field_data") or input_data.get("field_data")
    if not field_data:
        raise ValueError("webflow.create_collection_item requires 'field_data'")
    is_archived = config.get("isArchived", input_data.get("isArchived", False))
    is_draft = config.get("isDraft", input_data.get("isDraft", False))
    body = {"fieldData": field_data, "isArchived": is_archived, "isDraft": is_draft}
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/collections/{collection_id}/items", json=body)
    return _check(r)


@register_node("webflow.update_collection_item")
async def webflow_update_collection_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /collections/{collection_id}/items/{item_id} — update a collection item."""
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    item_id = config.get("item_id") or input_data.get("item_id")
    if not collection_id or not item_id:
        raise ValueError("webflow.update_collection_item requires 'collection_id' and 'item_id'")
    field_data = config.get("field_data") or input_data.get("field_data", {})
    body: dict = {}
    if field_data:
        body["fieldData"] = field_data
    for key in ("isArchived", "isDraft"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            body[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/collections/{collection_id}/items/{item_id}", json=body)
    return _check(r)


@register_node("webflow.delete_collection_item")
async def webflow_delete_collection_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /collections/{collection_id}/items/{item_id} — delete a collection item."""
    collection_id = config.get("collection_id") or input_data.get("collection_id")
    item_id = config.get("item_id") or input_data.get("item_id")
    if not collection_id or not item_id:
        raise ValueError("webflow.delete_collection_item requires 'collection_id' and 'item_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/collections/{collection_id}/items/{item_id}")
    if r.status_code == 204:
        return {"deleted": True, "item_id": item_id}
    return _check(r)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@register_node("webflow.list_pages")
async def webflow_list_pages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites/{site_id}/pages — list pages for a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("webflow.list_pages requires 'site_id'")
    params = {}
    for key in ("offset", "limit"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sites/{site_id}/pages", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------

@register_node("webflow.list_forms")
async def webflow_list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /sites/{site_id}/forms — list forms for a site."""
    site_id = config.get("site_id") or input_data.get("site_id")
    if not site_id:
        raise ValueError("webflow.list_forms requires 'site_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/sites/{site_id}/forms")
    return _check(r)


@register_node("webflow.list_form_submissions")
async def webflow_list_form_submissions(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /forms/{form_id}/submissions — list submissions for a form."""
    form_id = config.get("form_id") or input_data.get("form_id")
    if not form_id:
        raise ValueError("webflow.list_form_submissions requires 'form_id'")
    params = {}
    for key in ("offset", "limit"):
        v = config.get(key) or input_data.get(key)
        if v is not None:
            params[key] = v
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/forms/{form_id}/submissions", params=params)
    return _check(r)
