"""Short.io integration — link shortening and statistics."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SHORT_IO_BASE = "https://api.short.io"


def _short_io_headers(secret_key: str) -> dict:
    return {"Authorization": secret_key, "Content-Type": "application/json"}


@register_node("short_io.create_link")
async def short_io_create_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new short link with Short.io.

    config:
      secret_key   — Short.io secret API key (required)
      domain       — your Short.io domain e.g. "link.example.com" (required)
      original_url — destination URL to shorten (required)
      path         — custom path/slug (optional)
      title        — link title (optional)
      tags         — list of tag strings (optional)
    """
    merged = {**config, **input_data}
    secret_key = merged.get("secret_key", "")
    domain = merged.get("domain", "")
    original_url = merged.get("original_url")
    if not secret_key or not domain or not original_url:
        raise ValueError("secret_key, domain, and original_url are required for short_io.create_link")

    payload: dict = {"domain": domain, "originalURL": original_url}
    for field in ["path", "title", "tags"]:
        if merged.get(field):
            payload[field] = merged[field]

    async with httpx.AsyncClient(base_url=SHORT_IO_BASE, timeout=30) as client:
        r = await client.post("/links", headers=_short_io_headers(secret_key), json=payload)
        r.raise_for_status()
        link = r.json()

    link_id = link.get("id") or link.get("idString")
    short_url = link.get("shortURL")
    log.info("short_io.create_link", link_id=link_id, short_url=short_url)
    return {"link": link, "link_id": link_id, "short_url": short_url}


@register_node("short_io.update_link")
async def short_io_update_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing Short.io link.

    config:
      secret_key   — Short.io secret API key (required)
      link_id      — link ID to update (required)
      original_url — new destination URL (optional)
      path         — new custom path (optional)
      title        — new link title (optional)
    """
    merged = {**config, **input_data}
    secret_key = merged.get("secret_key", "")
    link_id = merged.get("link_id")
    if not secret_key or not link_id:
        raise ValueError("secret_key and link_id are required for short_io.update_link")

    payload = {k: v for k, v in {
        "originalURL": merged.get("original_url"),
        "path": merged.get("path"),
        "title": merged.get("title"),
    }.items() if v is not None}

    async with httpx.AsyncClient(base_url=SHORT_IO_BASE, timeout=30) as client:
        r = await client.post(f"/links/{link_id}", headers=_short_io_headers(secret_key), json=payload)
        r.raise_for_status()
        link = r.json()

    log.info("short_io.update_link", link_id=link_id)
    return {"link": link, "link_id": link_id}


@register_node("short_io.delete_link")
async def short_io_delete_link(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a Short.io link.

    config:
      secret_key — Short.io secret API key (required)
      link_id    — link ID to delete (required)
    """
    merged = {**config, **input_data}
    secret_key = merged.get("secret_key", "")
    link_id = merged.get("link_id")
    if not secret_key or not link_id:
        raise ValueError("secret_key and link_id are required for short_io.delete_link")

    async with httpx.AsyncClient(base_url=SHORT_IO_BASE, timeout=30) as client:
        r = await client.delete(f"/links/{link_id}", headers=_short_io_headers(secret_key))
        r.raise_for_status()

    log.info("short_io.delete_link", link_id=link_id)
    return {"success": True, "link_id": link_id}


@register_node("short_io.list_links")
async def short_io_list_links(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all links for a Short.io domain.

    config:
      secret_key — Short.io secret API key (required)
      domain_id  — numeric domain ID (required)
      limit      — number of links to return (optional, default 50)
      before     — pagination cursor (optional)
    """
    merged = {**config, **input_data}
    secret_key = merged.get("secret_key", "")
    domain_id = merged.get("domain_id")
    if not secret_key or not domain_id:
        raise ValueError("secret_key and domain_id are required for short_io.list_links")

    params: dict = {"domain_id": domain_id, "limit": merged.get("limit", 50)}
    if merged.get("before"):
        params["before"] = merged["before"]

    async with httpx.AsyncClient(base_url=SHORT_IO_BASE, timeout=30) as client:
        r = await client.get("/api/links", headers=_short_io_headers(secret_key), params=params)
        r.raise_for_status()
        data = r.json()

    links = data.get("links", data) if isinstance(data, dict) else data
    log.info("short_io.list_links", count=len(links) if isinstance(links, list) else 1)
    return {"links": links, "count": len(links) if isinstance(links, list) else None}


@register_node("short_io.get_statistics")
async def short_io_get_statistics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get click statistics for a Short.io link.

    config:
      secret_key — Short.io secret API key (required)
      link_id    — link ID to get stats for (required)
      period     — time period: today/week/month/quarter/year/all (optional, default month)
    """
    merged = {**config, **input_data}
    secret_key = merged.get("secret_key", "")
    link_id = merged.get("link_id")
    if not secret_key or not link_id:
        raise ValueError("secret_key and link_id are required for short_io.get_statistics")

    params: dict = {"period": merged.get("period", "month")}

    async with httpx.AsyncClient(base_url=SHORT_IO_BASE, timeout=30) as client:
        r = await client.get(
            f"/statistics/link/{link_id}",
            headers=_short_io_headers(secret_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    log.info("short_io.get_statistics", link_id=link_id, clicks=data.get("clicks"))
    return {"statistics": data, "link_id": link_id, "clicks": data.get("clicks")}
