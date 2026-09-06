"""SignRequest e-signature integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://signrequest.com/api/v1"


@register_node("signrequest.send_document")
async def signrequest_send_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a document for signing via SignRequest."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    document_url = merged.get("document_url", "")
    if not document_url:
        raise ValueError("document_url is required")
    payload = {
        "document": {"file_from_url": document_url},
        "from_email": merged.get("from_email", ""),
        "signers": merged.get("signers", []),
        "message": merged.get("message", ""),
        "subject": merged.get("subject", ""),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/signrequests/",
            headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        result = r.json()
    log.info("signrequest.send_document")
    return result


@register_node("signrequest.get_document")
async def signrequest_get_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a SignRequest document by UUID."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    uuid = merged.get("uuid", "")
    if not uuid:
        raise ValueError("uuid is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/signrequests/{uuid}/",
            headers={"Authorization": f"Token {api_key}"},
        )
        r.raise_for_status()
        result = r.json()
    log.info("signrequest.get_document")
    return result


@register_node("signrequest.list_documents")
async def signrequest_list_documents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List SignRequest documents."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{BASE_URL}/documents/",
            headers={"Authorization": f"Token {api_key}"},
            params={"limit": merged.get("limit", 20), "offset": merged.get("offset", 0)},
        )
        r.raise_for_status()
        result = r.json()
    log.info("signrequest.list_documents")
    return result


@register_node("signrequest.cancel_document")
async def signrequest_cancel_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Cancel a SignRequest document by UUID."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")
    uuid = merged.get("uuid", "")
    if not uuid:
        raise ValueError("uuid is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/signrequests/{uuid}/cancel_signrequest/",
            headers={"Authorization": f"Token {api_key}"},
        )
        r.raise_for_status()
        result = r.json()
    log.info("signrequest.cancel_document")
    return result
