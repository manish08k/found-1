"""
Mindee document AI integration.

Provides parsing of invoices, receipts, and passports via the Mindee API.

Credential fields:
  - api_key : Mindee API key

Auth: Authorization: Token <api_key> header.

Base URL: https://api.mindee.net/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.mindee.net/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Mindee credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Token {api_key}"},
        timeout=60.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mindee API error {r.status_code}: {detail}")


async def _parse_document(credential_id: str, db, endpoint: str, document_url: str | None, document_base64: str | None, filename: str) -> dict:
    """Shared helper to send a document to a Mindee prediction endpoint."""
    async with await _client(credential_id, db) as client:
        if document_url:
            # URL-based prediction
            r = await client.post(
                endpoint,
                json={"document": document_url},
            )
        elif document_base64:
            # Base64-encoded file upload
            import base64
            file_bytes = base64.b64decode(document_base64)
            files = {"document": (filename, file_bytes, "application/octet-stream")}
            r = await client.post(endpoint, files=files)
        else:
            raise ValueError("Either 'document_url' or 'document_base64' must be provided")

        _raise_for_status(r)
        data = r.json()

    return {
        "document": data.get("document", {}),
        "prediction": data.get("document", {}).get("inference", {}).get("prediction", {}),
        "raw": data,
    }


@register_node("mindee.parse_invoice")
async def mindee_parse_invoice(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse an invoice document using Mindee AI."""
    document_url = config.get("document_url") or input_data.get("document_url")
    document_base64 = config.get("document_base64") or input_data.get("document_base64")
    filename = config.get("filename") or input_data.get("filename", "invoice.pdf")

    if not document_url and not document_base64:
        raise ValueError("mindee.parse_invoice requires 'document_url' or 'document_base64'")

    log.info("mindee.parse_invoice", has_url=bool(document_url), filename=filename)
    return await _parse_document(
        credential_id, db,
        endpoint="/products/mindee/invoices/v4/predict",
        document_url=document_url,
        document_base64=document_base64,
        filename=filename,
    )


@register_node("mindee.parse_receipt")
async def mindee_parse_receipt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse a receipt document using Mindee AI."""
    document_url = config.get("document_url") or input_data.get("document_url")
    document_base64 = config.get("document_base64") or input_data.get("document_base64")
    filename = config.get("filename") or input_data.get("filename", "receipt.jpg")

    if not document_url and not document_base64:
        raise ValueError("mindee.parse_receipt requires 'document_url' or 'document_base64'")

    log.info("mindee.parse_receipt", has_url=bool(document_url), filename=filename)
    return await _parse_document(
        credential_id, db,
        endpoint="/products/mindee/expense_receipts/v5/predict",
        document_url=document_url,
        document_base64=document_base64,
        filename=filename,
    )


@register_node("mindee.parse_passport")
async def mindee_parse_passport(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse a passport document using Mindee AI."""
    document_url = config.get("document_url") or input_data.get("document_url")
    document_base64 = config.get("document_base64") or input_data.get("document_base64")
    filename = config.get("filename") or input_data.get("filename", "passport.jpg")

    if not document_url and not document_base64:
        raise ValueError("mindee.parse_passport requires 'document_url' or 'document_base64'")

    log.info("mindee.parse_passport", has_url=bool(document_url), filename=filename)
    return await _parse_document(
        credential_id, db,
        endpoint="/products/mindee/passport/v1/predict",
        document_url=document_url,
        document_base64=document_base64,
        filename=filename,
    )
