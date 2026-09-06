"""AI Answer question-answering service — handler for aianswer integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.aianswer.com/v1"


@register_node("aianswer.ask")
async def aianswer_ask(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Ask a question.

    config/input_data:
      api_key — API key or token (required)
      question — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    question = merged.get("question") or ""
    if not question:
        raise ValueError("question required for aianswer.ask")
    payload = {"question": question}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/ask", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("aianswer.ask")
    return {"data": data}

@register_node("aianswer.list_knowledge_bases")
async def aianswer_list_knowledge_bases(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List knowledge bases.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/knowledge-bases", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("aianswer.list_knowledge_bases")
    return {"data": data}

@register_node("aianswer.create_knowledge_base")
async def aianswer_create_knowledge_base(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a knowledge base.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    if not name:
        raise ValueError("name required for aianswer.create_knowledge_base")
    payload = {"name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/knowledge-bases", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("aianswer.create_knowledge_base")
    return {"data": data}
