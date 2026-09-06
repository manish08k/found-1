"""Airparser integration — AI-powered document parsing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.airparser.com"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


@register_node("airparser.parse_document")
async def airparser_parse_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    inbox_id = merged.get("inbox_id", "")
    file_url = merged.get("file_url", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/v1/inboxes/{inbox_id}/parse", json={"url": file_url})
        r.raise_for_status()
    return r.json()


@register_node("airparser.get_parsed_data")
async def airparser_get_parsed_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    document_id = merged.get("document_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/v1/documents/{document_id}")
        r.raise_for_status()
    return r.json()


@register_node("airparser.list_inboxes")
async def airparser_list_inboxes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/v1/inboxes")
        r.raise_for_status()
    return {"inboxes": r.json()}
