"""Dub integration — link shortening, management, and analytics."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DUB_BASE = "https://api.dub.co"


def _dub_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("dub.create_link")
async def dub_create_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new short link with Dub.

    config:
      api_key   — Dub API key (required)
      url       — destination URL to shorten (required)
      domain    — custom domain to use (optional)
      key       — custom slug/key (optional)
      title     — link title (optional)
      tags      — list of tag names (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    url = merged.get("url")
    if not api_key or not url:
        raise ValueError("api_key and url are required for dub.create_link")

    payload: dict = {"url": url}
    for field in ["domain", "key", "title", "tags"]:
        if merged.get(field):
            payload[field] = merged[field]

    async with httpx.AsyncClient(base_url=DUB_BASE, timeout=30) as client:
        r = await client.post("/links", headers=_dub_headers(api_key), json=payload)
        r.raise_for_status()
        link = r.json()

    log.info("dub.create_link", link_id=link.get("id"), short_link=link.get("shortLink"))
    return {"link": link, "link_id": link.get("id"), "short_link": link.get("shortLink")}


@register_node("dub.get_link")
async def dub_get_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Dub link.

    config:
      api_key — Dub API key (required)
      link_id — link ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    link_id = merged.get("link_id")
    if not api_key or not link_id:
        raise ValueError("api_key and link_id are required for dub.get_link")

    async with httpx.AsyncClient(base_url=DUB_BASE, timeout=30) as client:
        r = await client.get(f"/links/{link_id}", headers=_dub_headers(api_key))
        r.raise_for_status()
        link = r.json()

    log.info("dub.get_link", link_id=link_id)
    return {"link": link, "link_id": link_id}


@register_node("dub.list_links")
async def dub_list_links(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all links in a Dub workspace.

    config:
      api_key    — Dub API key (required)
      domain     — filter by domain (optional)
      tag_id     — filter by tag ID (optional)
      page       — page number (optional, default 1)
      page_size  — results per page (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for dub.list_links")

    params: dict = {"page": merged.get("page", 1), "pageSize": merged.get("page_size", 100)}
    for field in ["domain", "tagId"]:
        config_key = "tag_id" if field == "tagId" else field
        if merged.get(config_key):
            params[field] = merged[config_key]

    async with httpx.AsyncClient(base_url=DUB_BASE, timeout=30) as client:
        r = await client.get("/links", headers=_dub_headers(api_key), params=params)
        r.raise_for_status()
        links = r.json()

    log.info("dub.list_links", count=len(links))
    return {"links": links, "count": len(links)}


@register_node("dub.update_link")
async def dub_update_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing Dub link.

    config:
      api_key — Dub API key (required)
      link_id — link ID to update (required)
      url     — new destination URL (optional)
      title   — new link title (optional)
      tags    — new list of tag names (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    link_id = merged.get("link_id")
    if not api_key or not link_id:
        raise ValueError("api_key and link_id are required for dub.update_link")

    payload = {k: v for k, v in {
        "url": merged.get("url"),
        "title": merged.get("title"),
        "tags": merged.get("tags"),
    }.items() if v is not None}

    async with httpx.AsyncClient(base_url=DUB_BASE, timeout=30) as client:
        r = await client.patch(f"/links/{link_id}", headers=_dub_headers(api_key), json=payload)
        r.raise_for_status()
        link = r.json()

    log.info("dub.update_link", link_id=link_id)
    return {"link": link, "link_id": link_id}


@register_node("dub.delete_link")
async def dub_delete_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a Dub link.

    config:
      api_key — Dub API key (required)
      link_id — link ID to delete (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    link_id = merged.get("link_id")
    if not api_key or not link_id:
        raise ValueError("api_key and link_id are required for dub.delete_link")

    async with httpx.AsyncClient(base_url=DUB_BASE, timeout=30) as client:
        r = await client.delete(f"/links/{link_id}", headers=_dub_headers(api_key))
        r.raise_for_status()

    log.info("dub.delete_link", link_id=link_id)
    return {"success": True, "link_id": link_id}


@register_node("dub.get_analytics")
async def dub_get_analytics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get analytics for a Dub link.

    config:
      api_key   — Dub API key (required)
      link_id   — link ID (optional)
      domain    — filter by domain (optional)
      interval  — time interval: 1h/24h/7d/30d/90d/1y/all (optional, default 30d)
      event     — event type: clicks/leads/sales/composite (optional, default clicks)
      group_by  — dimension to group by (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for dub.get_analytics")

    params: dict = {
        "interval": merged.get("interval", "30d"),
        "event": merged.get("event", "clicks"),
    }
    for field in ["linkId", "domain", "groupBy"]:
        config_key = {"linkId": "link_id", "groupBy": "group_by"}.get(field, field)
        if merged.get(config_key):
            params[field] = merged[config_key]

    async with httpx.AsyncClient(base_url=DUB_BASE, timeout=30) as client:
        r = await client.get("/analytics", headers=_dub_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    log.info("dub.get_analytics", interval=params["interval"], event=params["event"])
    return {"analytics": data, "interval": params["interval"], "event": params["event"]}
