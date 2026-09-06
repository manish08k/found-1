"""DocumentPro integration — AI document processing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.documentpro.ai/v1"


def _headers(config: dict) -> dict:
    return {"X-API-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("documentpro.extract_data")
async def documentpro_extract_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/extract", json={
            "document_url": merged.get("document_url", ""),
            "template_id": merged.get("template_id", ""),
        })
        r.raise_for_status()
    return r.json()
