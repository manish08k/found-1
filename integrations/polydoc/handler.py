"""Polydoc integration — AI document analysis and Q&A."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.polydoc.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("polydoc.upload_document")
async def polydoc_upload_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/documents", json={"url": merged.get("url", "")})
        r.raise_for_status()
    return r.json()


@register_node("polydoc.ask_question")
async def polydoc_ask_question(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    doc_id = merged.get("document_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/documents/{doc_id}/ask", json={"question": merged.get("question", "")})
        r.raise_for_status()
    return r.json()
