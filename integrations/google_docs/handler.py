"""Google Docs integration — document creation and editing."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://docs.googleapis.com/v1"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("google_docs.create_document")
async def google_docs_create_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/documents", json={"title": merged.get("title", "Untitled Document")})
        r.raise_for_status()
    data = r.json()
    return {"document_id": data["documentId"], "title": data["title"], "url": f"https://docs.google.com/document/d/{data['documentId']}"}


@register_node("google_docs.get_document")
async def google_docs_get_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    doc_id = merged.get("document_id", "")
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/documents/{doc_id}")
        r.raise_for_status()
    data = r.json()
    return {"document_id": data["documentId"], "title": data["title"], "body": data.get("body", {})}


@register_node("google_docs.update_document")
async def google_docs_update_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    doc_id = merged.get("document_id", "")
    requests = merged.get("requests", [])
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/documents/{doc_id}:batchUpdate", json={"requests": requests})
        r.raise_for_status()
    return r.json()


@register_node("google_docs.append_text")
async def google_docs_append_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    doc_id = merged.get("document_id", "")
    text = merged.get("text", "")
    headers = await _headers(credential_id, db)
    requests = [{"insertText": {"location": {"index": 1}, "text": text}}]
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/documents/{doc_id}:batchUpdate", json={"requests": requests})
        r.raise_for_status()
    return {"document_id": doc_id, "text_appended": text}
