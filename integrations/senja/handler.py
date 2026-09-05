"""Senja — testimonials collection and management integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SENJA_BASE = "https://api.senja.io/v1"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("senja.list_testimonials")
async def senja_list_testimonials(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List testimonials from Senja.

    config:
      api_key — Senja API key
      limit   — number of testimonials to return (default 25)
    """
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=SENJA_BASE, timeout=30) as client:
        r = await client.get("/testimonials", params={"limit": limit}, headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    testimonials = data.get("data", data if isinstance(data, list) else [])
    log.info("senja.list_testimonials", count=len(testimonials))
    return {"testimonials": testimonials, "count": len(testimonials)}


@register_node("senja.create_testimonial")
async def senja_create_testimonial(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new testimonial in Senja.

    config/input_data:
      api_key      — Senja API key
      content      — testimonial text content (required)
      author_name  — author's display name (required)
      author_email — author's email address (optional)
    """
    content = config.get("content") or input_data.get("content")
    author_name = config.get("author_name") or input_data.get("author_name")
    author_email = config.get("author_email") or input_data.get("author_email", "")

    if not content:
        raise ValueError("content is required for senja.create_testimonial")
    if not author_name:
        raise ValueError("author_name is required for senja.create_testimonial")

    payload: dict = {"content": content, "author_name": author_name}
    if author_email:
        payload["author_email"] = author_email

    async with httpx.AsyncClient(base_url=SENJA_BASE, timeout=30) as client:
        r = await client.post("/testimonials", json=payload, headers=_headers(config))
        r.raise_for_status()
        testimonial = r.json()

    log.info("senja.create_testimonial", author_name=author_name)
    return {"testimonial": testimonial, "id": testimonial.get("id"), "author_name": author_name}


@register_node("senja.list_forms")
async def senja_list_forms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List testimonial collection forms from Senja.

    config:
      api_key — Senja API key
    """
    async with httpx.AsyncClient(base_url=SENJA_BASE, timeout=30) as client:
        r = await client.get("/forms", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    forms = data.get("data", data if isinstance(data, list) else [])
    log.info("senja.list_forms", count=len(forms))
    return {"forms": forms, "count": len(forms)}
