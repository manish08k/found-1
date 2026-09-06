"""Doctly integration — document processing and data extraction."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.doctly.ai/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("doctly.process_document")
async def doctly_process_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/documents/process", json={
            "url": merged.get("url", ""),
            "document_type": merged.get("document_type", "invoice"),
        })
        r.raise_for_status()
    return r.json()


@register_node("doctly.get_extraction")
async def doctly_get_extraction(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    doc_id = merged.get("document_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/documents/{doc_id}/extraction")
        r.raise_for_status()
    return r.json()
