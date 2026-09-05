"""Podio collaboration platform integration — items."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PODIO_BASE = "https://api.podio.com"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"OAuth2 {access_token}", "Accept": "application/json"}


@register_node("podio.list_items")
async def podio_list_items(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List items from a Podio app.

    config:
      access_token — Podio OAuth2 access token (required)
      app_id       — Podio app ID (required)
      limit        — max items to return (default 25)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for podio.list_items")

    app_id = config.get("app_id") or input_data.get("app_id")
    if not app_id:
        raise ValueError("app_id is required for podio.list_items")

    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=PODIO_BASE, timeout=30) as client:
        r = await client.get(
            f"/item/app/{app_id}/",
            params={"limit": limit},
            headers=_headers(access_token),
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    total = data.get("total", len(items))
    log.info("podio.list_items", app_id=app_id, count=len(items))
    return {"items": items, "count": len(items), "total": total}


@register_node("podio.get_item")
async def podio_get_item(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Podio item by ID.

    config/input_data:
      access_token — Podio OAuth2 access token (required)
      item_id      — item ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for podio.get_item")

    item_id = config.get("item_id") or input_data.get("item_id")
    if not item_id:
        raise ValueError("item_id is required for podio.get_item")

    async with httpx.AsyncClient(base_url=PODIO_BASE, timeout=30) as client:
        r = await client.get(f"/item/{item_id}", headers=_headers(access_token))
        r.raise_for_status()
        item = r.json()

    log.info("podio.get_item", item_id=item_id)
    return {"item": item}


@register_node("podio.create_item")
async def podio_create_item(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an item in a Podio app.

    config/input_data:
      access_token — Podio OAuth2 access token (required)
      app_id       — Podio app ID (required)
      field_id     — external_id of the field to populate (required)
      value        — value to set for the field (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for podio.create_item")

    app_id = config.get("app_id") or input_data.get("app_id")
    field_id = config.get("field_id") or input_data.get("field_id")
    val = config.get("value") or input_data.get("value")
    if not app_id or not field_id:
        raise ValueError("app_id and field_id are required for podio.create_item")

    payload = {"fields": [{"external_id": field_id, "values": [{"value": val}]}]}

    async with httpx.AsyncClient(base_url=PODIO_BASE, timeout=30) as client:
        r = await client.post(f"/item/app/{app_id}/", json=payload, headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    item_id = data.get("item_id")
    log.info("podio.create_item", app_id=app_id, item_id=item_id)
    return {"result": data, "item_id": item_id}
