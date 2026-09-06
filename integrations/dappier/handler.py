"""Dappier AI-powered data and search integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DAPPIER_BASE = "https://api.dappier.com/app"


@register_node("dappier.search")
async def dappier_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search using a Dappier AI data model.

    config/input_data:
      api_key        — Dappier API key
      ai_model_id    — AI model ID (e.g. am_01j0ryv2gxfysyanb55tbtam4t)
      query          — search query
      num_articles   — optional number of articles to return (default 5)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    ai_model_id = merged.get("ai_model_id", "")
    if not ai_model_id:
        raise ValueError("ai_model_id is required")
    query = merged.get("query", "")
    if not query:
        raise ValueError("query is required")

    payload = {
        "query": query,
        "num_articles_ref": merged.get("num_articles", 5),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DAPPIER_BASE}/aimodel/{ai_model_id}/search",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("dappier.search", ai_model_id=ai_model_id, query=query)
    return result


@register_node("dappier.recommend")
async def dappier_recommend(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get content recommendations from a Dappier data model.

    config/input_data:
      api_key      — Dappier API key
      ai_model_id  — AI model ID
      query        — reference content or topic for recommendations
      num_articles — optional number of recommendations (default 5)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    ai_model_id = merged.get("ai_model_id", "")
    if not ai_model_id:
        raise ValueError("ai_model_id is required")
    query = merged.get("query", "")
    if not query:
        raise ValueError("query is required")

    payload = {
        "query": query,
        "num_articles_ref": merged.get("num_articles", 5),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{DAPPIER_BASE}/aimodel/{ai_model_id}/recommend",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("dappier.recommend", ai_model_id=ai_model_id)
    return result


@register_node("dappier.get_data_model")
async def dappier_get_data_model(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a Dappier AI data model.

    config/input_data:
      api_key     — Dappier API key
      ai_model_id — AI model ID to retrieve
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    ai_model_id = merged.get("ai_model_id", "")
    if not ai_model_id:
        raise ValueError("ai_model_id is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{DAPPIER_BASE}/aimodel/{ai_model_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("dappier.get_data_model", ai_model_id=ai_model_id)
    return result
