"""SignNow integration — document creation, signing invitations, and downloads."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SIGNNOW_SANDBOX_BASE = "https://api-eval.signnow.com"
SIGNNOW_PROD_BASE = "https://api.signnow.com"


def _signnow_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def _signnow_base(config: dict) -> str:
    if config.get("sandbox", True):
        return SIGNNOW_SANDBOX_BASE
    return SIGNNOW_PROD_BASE


@register_node("sign_now.create_document")
async def sign_now_create_document(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Upload a document to SignNow.

    config:
      access_token  — SignNow OAuth bearer token (required)
      sandbox       — use sandbox environment (optional, default True)
      file_content  — base64-encoded PDF file content (required)
      filename      — name for the uploaded file e.g. "contract.pdf" (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    base_url = _signnow_base(merged)
    file_content_b64 = merged.get("file_content")
    filename = merged.get("filename", "document.pdf")

    if not file_content_b64:
        raise ValueError("file_content is required for sign_now.create_document")

    import base64 as _b64
    file_bytes = _b64.b64decode(file_content_b64)

    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        r = await client.post(
            "/document",
            headers=headers,
            files={"file": (filename, file_bytes, "application/pdf")},
        )
        r.raise_for_status()
        data = r.json()

    document_id = data.get("id")
    log.info("sign_now.create_document", document_id=document_id, filename=filename)
    return {"document": data, "document_id": document_id}


@register_node("sign_now.get_document")
async def sign_now_get_document(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get details of a SignNow document.

    config:
      access_token — SignNow OAuth bearer token (required)
      sandbox      — use sandbox environment (optional, default True)
      document_id  — document ID (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    base_url = _signnow_base(merged)
    document_id = merged.get("document_id")

    if not document_id:
        raise ValueError("document_id is required for sign_now.get_document")

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.get(
            f"/document/{document_id}", headers=_signnow_headers(access_token)
        )
        r.raise_for_status()
        document = r.json()

    log.info("sign_now.get_document", document_id=document_id)
    return {"document": document, "document_id": document_id}


@register_node("sign_now.invite_signers")
async def sign_now_invite_signers(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Send signing invitations for a SignNow document.

    config:
      access_token — SignNow OAuth bearer token (required)
      sandbox      — use sandbox environment (optional, default True)
      document_id  — document ID to send for signing (required)
      from_email   — sender email address (required)
      to           — list of signer dicts with email, role, order (required)
      subject      — email subject line (optional)
      message      — email body message (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    base_url = _signnow_base(merged)
    document_id = merged.get("document_id")
    from_email = merged.get("from_email")
    to = merged.get("to", [])

    if not document_id or not from_email or not to:
        raise ValueError(
            "document_id, from_email, and to are required for sign_now.invite_signers"
        )

    payload: dict = {
        "from": from_email,
        "to": to,
    }
    if merged.get("subject"):
        payload["subject"] = merged["subject"]
    if merged.get("message"):
        payload["message"] = merged["message"]

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.post(
            f"/document/{document_id}/invite",
            headers=_signnow_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    log.info("sign_now.invite_signers", document_id=document_id, signer_count=len(to))
    return {"result": data, "document_id": document_id}


@register_node("sign_now.list_documents")
async def sign_now_list_documents(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List documents in the SignNow account.

    config:
      access_token — SignNow OAuth bearer token (required)
      sandbox      — use sandbox environment (optional, default True)
      per_page     — results per page (optional, default 20)
      page         — page number starting at 0 (optional, default 0)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    base_url = _signnow_base(merged)

    params = {
        "per_page": merged.get("per_page", 20),
        "page": merged.get("page", 0),
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        r = await client.get(
            "/user/documentsv2",
            headers=_signnow_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    documents = data if isinstance(data, list) else data.get("documents", [])
    log.info("sign_now.list_documents", count=len(documents))
    return {"documents": documents, "count": len(documents)}


@register_node("sign_now.download_document")
async def sign_now_download_document(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Download a completed SignNow document as a PDF.

    config:
      access_token — SignNow OAuth bearer token (required)
      sandbox      — use sandbox environment (optional, default True)
      document_id  — document ID to download (required)
      with_history — include signing history in the PDF (optional, default False)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    base_url = _signnow_base(merged)
    document_id = merged.get("document_id")

    if not document_id:
        raise ValueError("document_id is required for sign_now.download_document")

    params: dict = {}
    if merged.get("with_history"):
        params["with_history"] = 1

    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        r = await client.get(
            f"/document/{document_id}/download",
            headers=headers,
            params=params,
        )
        r.raise_for_status()
        content = r.content

    log.info("sign_now.download_document", document_id=document_id, size=len(content))
    return {
        "document_id": document_id,
        "content_type": "application/pdf",
        "size": len(content),
        "content_hex": content.hex(),
    }
