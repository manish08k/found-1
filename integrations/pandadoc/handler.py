"""PandaDoc integration — documents, templates, and sending."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PANDADOC_BASE = "https://api.pandadoc.com/public/v1"


def _pandadoc_headers(api_key: str) -> dict:
    return {
        "Authorization": f"API-Key {api_key}",
        "Content-Type": "application/json",
    }


@register_node("pandadoc.list_documents")
async def pandadoc_list_documents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List documents in PandaDoc.

    config:
      api_key  — PandaDoc API key (required)
      status   — filter by status: 0=draft, 1=sent, etc. (optional)
      page     — page number (optional, default 1)
      count    — results per page (optional, default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pandadoc.list_documents")

    params: dict = {"page": merged.get("page", 1), "count": merged.get("count", 25)}
    if merged.get("status") is not None:
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=PANDADOC_BASE, timeout=30) as client:
        r = await client.get("/documents", headers=_pandadoc_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    documents = data.get("results", [])
    log.info("pandadoc.list_documents", count=len(documents))
    return {"documents": documents, "count": len(documents)}


@register_node("pandadoc.get_document")
async def pandadoc_get_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific PandaDoc document.

    config:
      api_key     — PandaDoc API key (required)
      document_id — document ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    document_id = merged.get("document_id")
    if not api_key or not document_id:
        raise ValueError("api_key and document_id are required")

    async with httpx.AsyncClient(base_url=PANDADOC_BASE, timeout=30) as client:
        r = await client.get(f"/documents/{document_id}", headers=_pandadoc_headers(api_key))
        r.raise_for_status()
        document = r.json()

    log.info("pandadoc.get_document", document_id=document_id, status=document.get("status"))
    return {"document": document, "document_id": document_id}


@register_node("pandadoc.create_document")
async def pandadoc_create_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a PandaDoc document from a template.

    config:
      api_key     — PandaDoc API key (required)
      name        — document name (required)
      template_id — template UUID to use (optional)
      recipients  — list of recipient dicts with email/first_name/last_name/role (required)
      fields      — dict of template field values (optional)
      tokens      — list of token dicts with name/value (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pandadoc.create_document")

    payload: dict = {
        "name": merged.get("name", "Untitled Document"),
        "recipients": merged.get("recipients", []),
    }
    if merged.get("template_id"):
        payload["template_uuid"] = merged["template_id"]
    if merged.get("fields"):
        payload["fields"] = merged["fields"]
    if merged.get("tokens"):
        payload["tokens"] = merged["tokens"]

    async with httpx.AsyncClient(base_url=PANDADOC_BASE, timeout=30) as client:
        r = await client.post("/documents", headers=_pandadoc_headers(api_key), json=payload)
        r.raise_for_status()
        document = r.json()

    document_id = document.get("id") or document.get("uuid")
    log.info("pandadoc.create_document", document_id=document_id)
    return {"document": document, "document_id": document_id}


@register_node("pandadoc.send_document")
async def pandadoc_send_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a PandaDoc document to recipients for signing.

    config:
      api_key     — PandaDoc API key (required)
      document_id — document ID to send (required)
      subject     — email subject (optional)
      message     — email message body (optional)
      silent      — send without email notification: true/false (optional, default false)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    document_id = merged.get("document_id")
    if not api_key or not document_id:
        raise ValueError("api_key and document_id are required")

    payload: dict = {"silent": merged.get("silent", False)}
    if merged.get("subject"):
        payload["subject"] = merged["subject"]
    if merged.get("message"):
        payload["message"] = merged["message"]

    async with httpx.AsyncClient(base_url=PANDADOC_BASE, timeout=30) as client:
        r = await client.post(
            f"/documents/{document_id}/send",
            headers=_pandadoc_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    log.info("pandadoc.send_document", document_id=document_id)
    return {"result": data, "document_id": document_id}


@register_node("pandadoc.download_document")
async def pandadoc_download_document(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Download a PandaDoc document as PDF (returns base64 content).

    config:
      api_key     — PandaDoc API key (required)
      document_id — document ID to download (required)
    """
    import base64

    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    document_id = merged.get("document_id")
    if not api_key or not document_id:
        raise ValueError("api_key and document_id are required")

    async with httpx.AsyncClient(base_url=PANDADOC_BASE, timeout=60) as client:
        r = await client.get(
            f"/documents/{document_id}/download",
            headers=_pandadoc_headers(api_key),
        )
        r.raise_for_status()
        pdf_bytes = r.content

    pdf_b64 = base64.b64encode(pdf_bytes).decode()
    log.info("pandadoc.download_document", document_id=document_id, size_bytes=len(pdf_bytes))
    return {"pdf_base64": pdf_b64, "document_id": document_id, "size_bytes": len(pdf_bytes)}


@register_node("pandadoc.list_templates")
async def pandadoc_list_templates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available PandaDoc templates.

    config:
      api_key — PandaDoc API key (required)
      tag     — filter by template tag (optional)
      page    — page number (optional, default 1)
      count   — results per page (optional, default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pandadoc.list_templates")

    params: dict = {"page": merged.get("page", 1), "count": merged.get("count", 25)}
    if merged.get("tag"):
        params["tag"] = merged["tag"]

    async with httpx.AsyncClient(base_url=PANDADOC_BASE, timeout=30) as client:
        r = await client.get("/templates", headers=_pandadoc_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    templates = data.get("results", [])
    log.info("pandadoc.list_templates", count=len(templates))
    return {"templates": templates, "count": len(templates)}
