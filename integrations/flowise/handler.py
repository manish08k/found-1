"""Flowise AI chatflow builder — handler for flowise integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "http://localhost:3000/api/v1"


@register_node("flowise.predict")
async def flowise_predict(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a chatflow prediction.

    config/input_data:
      api_key — API key or token (required)
      chatflow_id — (required)
      question — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    chatflow_id = merged.get("chatflow_id") or ""
    question = merged.get("question") or ""
    if not chatflow_id or not question:
        raise ValueError("chatflow_id, question required for flowise.predict")
    payload = {"question": question}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/prediction/{chatflow_id}", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("flowise.predict")
    return {"data": data}

@register_node("flowise.list_chatflows")
async def flowise_list_chatflows(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List chatflows.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/chatflows", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("flowise.list_chatflows")
    return {"data": data}

@register_node("flowise.get_chatflow")
async def flowise_get_chatflow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get chatflow details.

    config/input_data:
      api_key — API key or token (required)
      chatflow_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    chatflow_id = merged.get("chatflow_id") or ""
    if not chatflow_id:
        raise ValueError("chatflow_id required for flowise.get_chatflow")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/chatflows/{chatflow_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("flowise.get_chatflow")
    return {"data": data}
