"""Medullar AI knowledge management — handler for medullar integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.medullar.com/v1"


@register_node("medullar.query")
async def medullar_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query knowledge base.

    config/input_data:
      api_key — API key or token (required)
      question — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    question = merged.get("question") or ""
    if not question:
        raise ValueError("question required for medullar.query")
    payload = {"question": question}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/query", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("medullar.query")
    return {"data": data}

@register_node("medullar.list_sources")
async def medullar_list_sources(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List knowledge sources.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/sources", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("medullar.list_sources")
    return {"data": data}

@register_node("medullar.add_source")
async def medullar_add_source(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a knowledge source.

    config/input_data:
      api_key — API key or token (required)
      url — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = merged.get("url") or ""
    if not url:
        raise ValueError("url required for medullar.add_source")
    payload = {"url": url}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/sources", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("medullar.add_source")
    return {"data": data}
