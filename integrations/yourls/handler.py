"""YOURLS integration — self-hosted URL shortening and statistics."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _yourls_auth_params(merged: dict) -> dict:
    """Return auth params: signature preferred, otherwise username+password."""
    if merged.get("signature"):
        return {"signature": merged["signature"]}
    return {
        "username": merged.get("username", ""),
        "password": merged.get("password", ""),
    }


@register_node("yourls.shorten")
async def yourls_shorten(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Shorten a URL using YOURLS.

    config:
      base_url  — base URL of YOURLS installation e.g. https://yoursite.com (required)
      signature — YOURLS API signature token (or use username+password)
      url       — long URL to shorten (required)
      keyword   — optional custom alias
      title     — optional title for the short URL
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    url = merged.get("url")
    if not base_url or not url:
        raise ValueError("base_url and url are required for yourls.shorten")

    params = {
        "format": "json",
        "action": "shorturl",
        "url": url,
        **_yourls_auth_params(merged),
    }
    if merged.get("keyword"):
        params["keyword"] = merged["keyword"]
    if merged.get("title"):
        params["title"] = merged["title"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/yourls-api.php", data=params)
        r.raise_for_status()
        data = r.json()

    shorturl = data.get("shorturl", "")
    longurl = data.get("url", {})
    if isinstance(longurl, dict):
        longurl = longurl.get("url", url)
    title = data.get("title", "")

    log.info("yourls.shorten", shorturl=shorturl)
    return {"shorturl": shorturl, "longurl": longurl, "title": title, "response": data}


@register_node("yourls.expand")
async def yourls_expand(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Expand a YOURLS short URL to its original long URL.

    config:
      base_url  — base URL of YOURLS installation (required)
      signature — YOURLS API signature token (or use username+password)
      shorturl  — the short URL or keyword to expand (required)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    shorturl = merged.get("shorturl")
    if not base_url or not shorturl:
        raise ValueError("base_url and shorturl are required for yourls.expand")

    params = {
        "format": "json",
        "action": "expand",
        "shorturl": shorturl,
        **_yourls_auth_params(merged),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/yourls-api.php", data=params)
        r.raise_for_status()
        data = r.json()

    longurl = data.get("longurl", "")
    log.info("yourls.expand", shorturl=shorturl, longurl=longurl)
    return {"longurl": longurl, "shorturl": shorturl, "response": data}


@register_node("yourls.url_stats")
async def yourls_url_stats(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get click and traffic statistics for a specific YOURLS short URL.

    config:
      base_url  — base URL of YOURLS installation (required)
      signature — YOURLS API signature token (or use username+password)
      shorturl  — the short URL or keyword (required)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    shorturl = merged.get("shorturl")
    if not base_url or not shorturl:
        raise ValueError("base_url and shorturl are required for yourls.url_stats")

    params = {
        "format": "json",
        "action": "url-stats",
        "shorturl": shorturl,
        **_yourls_auth_params(merged),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/yourls-api.php", data=params)
        r.raise_for_status()
        data = r.json()

    log.info("yourls.url_stats", shorturl=shorturl)
    return {"stats": data.get("link", {}), "response": data}


@register_node("yourls.db_stats")
async def yourls_db_stats(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get global YOURLS database statistics (total links, clicks).

    config:
      base_url  — base URL of YOURLS installation (required)
      signature — YOURLS API signature token (or use username+password)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    if not base_url:
        raise ValueError("base_url is required for yourls.db_stats")

    params = {
        "format": "json",
        "action": "db-stats",
        **_yourls_auth_params(merged),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{base_url}/yourls-api.php", data=params)
        r.raise_for_status()
        data = r.json()

    log.info("yourls.db_stats")
    return {"db-stats": data.get("db-stats", {}), "response": data}
