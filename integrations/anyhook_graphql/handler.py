"""Anyhook GraphQL webhook service — handler for anyhook_graphql integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.anyhook.io/graphql"


@register_node("anyhook_graphql.execute_query")
async def anyhook_graphql_execute_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a GraphQL query.

    config/input_data:
      api_key — API key or token (required)
      query — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    query = merged.get("query") or ""
    if not query:
        raise ValueError("query required for anyhook_graphql.execute_query")
    payload = {"query": query}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("anyhook_graphql.execute_query")
    return {"data": data}
