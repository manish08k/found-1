"""Parser Expert document parsing integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERVICE_BASE = "https://api.parserexpert.com/v1"


@register_node("parser_expert.parse_document")
async def parser_expert_parse_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Parse a document using Parser Expert."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for parser_expert.parse_document")
    document_url = merged.get("document_url", "")
    parser_id = merged.get("parser_id", "")
    if not document_url:
        raise ValueError("document_url is required for parser_expert.parse_document")
    payload = {"document_url": document_url}
    if parser_id:
        payload["parser_id"] = parser_id
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post("/parse", headers={"Authorization": f"Bearer {api_key}"}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("parser_expert.parse_document", document_url=document_url)
    return {"parsed": data}


@register_node("parser_expert.extract_data")
async def parser_expert_extract_data(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Extract structured data from a document using Parser Expert."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for parser_expert.extract_data")
    document_id = merged.get("document_id", "")
    fields = merged.get("fields", [])
    if not document_id:
        raise ValueError("document_id is required for parser_expert.extract_data")
    payload = {"document_id": document_id}
    if fields:
        payload["fields"] = fields
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post("/extract", headers={"Authorization": f"Bearer {api_key}"}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("parser_expert.extract_data", document_id=document_id)
    return {"extracted": data}


@register_node("parser_expert.list_parsers")
async def parser_expert_list_parsers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available parsers in Parser Expert."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for parser_expert.list_parsers")
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get("/parsers", headers={"Authorization": f"Bearer {api_key}"})
        r.raise_for_status()
        data = r.json()
    parsers = data if isinstance(data, list) else data.get("parsers", [])
    log.info("parser_expert.list_parsers", count=len(parsers))
    return {"parsers": parsers}
