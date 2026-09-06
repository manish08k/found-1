"""Denser AI retrieval-augmented generation integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DENSER_BASE = "https://api.denser.ai/v1"


@register_node("denser_ai.search")
async def denser_ai_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search a Denser AI retriever with a query.

    config/input_data:
      api_key      — Denser AI API key
      retriever_id — ID of the retriever to search
      query        — search query text
      top_k        — optional number of results (default 5)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    retriever_id = merged.get("retriever_id", "")
    if not retriever_id:
        raise ValueError("retriever_id is required")
    query = merged.get("query", "")
    if not query:
        raise ValueError("query is required")

    payload = {
        "query": query,
        "top_k": merged.get("top_k", 5),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{DENSER_BASE}/retrievers/{retriever_id}/search",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("denser_ai.search", retriever_id=retriever_id, query=query)
    return result


@register_node("denser_ai.list_retrievers")
async def denser_ai_list_retrievers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Denser AI retrievers.

    config/input_data:
      api_key — Denser AI API key
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{DENSER_BASE}/retrievers",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("denser_ai.list_retrievers")
    return result


@register_node("denser_ai.create_document")
async def denser_ai_create_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a document to a Denser AI retriever.

    config/input_data:
      api_key      — Denser AI API key
      retriever_id — ID of the retriever
      content      — document text content
      metadata     — optional dict of metadata
      document_id  — optional external document ID
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    retriever_id = merged.get("retriever_id", "")
    if not retriever_id:
        raise ValueError("retriever_id is required")
    content = merged.get("content", "")
    if not content:
        raise ValueError("content is required")

    payload: dict = {"content": content}
    if merged.get("metadata"):
        payload["metadata"] = merged["metadata"]
    if merged.get("document_id"):
        payload["document_id"] = merged["document_id"]

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{DENSER_BASE}/retrievers/{retriever_id}/documents",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("denser_ai.create_document", retriever_id=retriever_id)
    return result
