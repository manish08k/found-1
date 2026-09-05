"""Wistia video marketing integration — media, projects, stats."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

WISTIA_BASE = "https://api.wistia.com/v1"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"}


@register_node("wistia.list_medias")
async def wistia_list_medias(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Wistia media objects (videos, images, etc).

    config/input_data:
      api_key  — Wistia API key (required)
      per_page — items per page (default 25)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for wistia.list_medias")
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=WISTIA_BASE, timeout=30) as client:
        r = await client.get("/medias.json", headers=_headers(api_key), params={"per_page": per_page})
        r.raise_for_status()
        medias = r.json()

    medias = medias if isinstance(medias, list) else []
    log.info("wistia.list_medias", count=len(medias))
    return {"medias": medias, "count": len(medias)}


@register_node("wistia.get_media")
async def wistia_get_media(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get Wistia media details by hashed ID.

    config/input_data:
      api_key   — Wistia API key (required)
      hashed_id — Wistia media hashed ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for wistia.get_media")
    hashed_id = config.get("hashed_id") or input_data.get("hashed_id")
    if not hashed_id:
        raise ValueError("hashed_id is required for wistia.get_media")

    async with httpx.AsyncClient(base_url=WISTIA_BASE, timeout=30) as client:
        r = await client.get(f"/medias/{hashed_id}.json", headers=_headers(api_key))
        r.raise_for_status()
        media = r.json()

    log.info("wistia.get_media", hashed_id=hashed_id, name=media.get("name"))
    return {"media": media, "hashed_id": hashed_id}


@register_node("wistia.list_projects")
async def wistia_list_projects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Wistia projects.

    config/input_data:
      api_key — Wistia API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for wistia.list_projects")

    async with httpx.AsyncClient(base_url=WISTIA_BASE, timeout=30) as client:
        r = await client.get("/projects.json", headers=_headers(api_key))
        r.raise_for_status()
        projects = r.json()

    projects = projects if isinstance(projects, list) else []
    log.info("wistia.list_projects", count=len(projects))
    return {"projects": projects, "count": len(projects)}


@register_node("wistia.get_stats")
async def wistia_get_stats(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get statistics for a Wistia media object.

    config/input_data:
      api_key   — Wistia API key (required)
      hashed_id — Wistia media hashed ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for wistia.get_stats")
    hashed_id = config.get("hashed_id") or input_data.get("hashed_id")
    if not hashed_id:
        raise ValueError("hashed_id is required for wistia.get_stats")

    async with httpx.AsyncClient(base_url=WISTIA_BASE, timeout=30) as client:
        r = await client.get(f"/medias/{hashed_id}/stats.json", headers=_headers(api_key))
        r.raise_for_status()
        stats = r.json()

    log.info("wistia.get_stats", hashed_id=hashed_id)
    return {"stats": stats, "hashed_id": hashed_id}
