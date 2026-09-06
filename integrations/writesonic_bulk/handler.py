"""Writesonic AI bulk content generation — handler for writesonic_bulk integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.writesonic.com/v2"


@register_node("writesonic_bulk.generate_article")
async def writesonic_bulk_generate_article(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate an article.

    config/input_data:
      api_key — API key or token (required)
      topic — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    topic = merged.get("topic") or ""
    if not topic:
        raise ValueError("topic required for writesonic_bulk.generate_article")
    payload = {"topic": topic}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/business/content/ai-article-writer-v3", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("writesonic_bulk.generate_article")
    return {"data": data}

@register_node("writesonic_bulk.list_content")
async def writesonic_bulk_list_content(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List generated content.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/business/content/list", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("writesonic_bulk.list_content")
    return {"data": data}
