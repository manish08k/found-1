"""Extracta AI integration — document data extraction."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://extracta.ai/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("extracta_ai.extract_document")
async def extracta_ai_extract_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/extract", json={
            "document_url": merged.get("document_url", ""),
            "extraction_template": merged.get("extraction_template", {}),
        })
        r.raise_for_status()
    return r.json()
