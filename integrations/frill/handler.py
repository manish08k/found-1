"""Frill — product feedback and announcements integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FRILL_BASE = "https://v1.frill.co/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("frill.list_ideas")
async def frill_list_ideas(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List ideas/feature requests from Frill.

    config:
      api_key — Frill API key
    """
    async with httpx.AsyncClient(base_url=FRILL_BASE, timeout=30) as client:
        r = await client.get("/ideas", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    ideas = data.get("ideas", data if isinstance(data, list) else [])
    log.info("frill.list_ideas", count=len(ideas))
    return {"ideas": ideas, "count": len(ideas)}


@register_node("frill.create_idea")
async def frill_create_idea(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new idea in Frill.

    config/input_data:
      api_key     — Frill API key
      title       — idea title (required)
      description — idea description (optional)
    """
    title = config.get("title") or input_data.get("title")
    description = config.get("description") or input_data.get("description", "")

    if not title:
        raise ValueError("title is required for frill.create_idea")

    async with httpx.AsyncClient(base_url=FRILL_BASE, timeout=30) as client:
        r = await client.post(
            "/ideas",
            json={"title": title, "description": description},
            headers=_headers(config),
        )
        r.raise_for_status()
        idea = r.json()

    log.info("frill.create_idea", title=title)
    return {"idea": idea, "id": idea.get("id"), "title": title}


@register_node("frill.list_announcements")
async def frill_list_announcements(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List announcements from Frill.

    config:
      api_key — Frill API key
    """
    async with httpx.AsyncClient(base_url=FRILL_BASE, timeout=30) as client:
        r = await client.get("/announcements", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    announcements = data.get("announcements", data if isinstance(data, list) else [])
    log.info("frill.list_announcements", count=len(announcements))
    return {"announcements": announcements, "count": len(announcements)}
