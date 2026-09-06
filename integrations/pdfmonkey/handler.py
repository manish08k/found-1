"""PDFMonkey integration — generate and manage PDF documents from templates."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PDFMONKEY_BASE = "https://api.pdfmonkey.io/api/v1"


def _pdfmonkey_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("pdfmonkey.generate_document")
async def pdfmonkey_generate_document(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Generate a PDF document from a PDFMonkey template.

    config:
      api_key     — PDFMonkey API key (required)
      template_id — ID of the template to use (required)
      payload     — dict of data to merge into the template (required)
      meta        — optional metadata dict to attach to the document (optional)
      status      — "pending" to generate async, or "draft" (optional, default "pending")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    template_id = merged.get("template_id")
    payload = merged.get("payload", {})

    if not template_id:
        raise ValueError("template_id is required for pdfmonkey.generate_document")
    if not payload:
        raise ValueError("payload dict is required for pdfmonkey.generate_document")

    body: dict = {
        "document": {
            "document_template_id": template_id,
            "payload": payload,
            "status": merged.get("status", "pending"),
        }
    }
    if merged.get("meta"):
        body["document"]["meta"] = merged["meta"]

    async with httpx.AsyncClient(base_url=PDFMONKEY_BASE, timeout=60) as client:
        r = await client.post(
            "/documents", headers=_pdfmonkey_headers(api_key), json=body
        )
        r.raise_for_status()
        data = r.json()

    document = data.get("document", data)
    log.info(
        "pdfmonkey.generate_document",
        document_id=document.get("id"),
        status=document.get("status"),
    )
    return {"document": document, "document_id": document.get("id")}


@register_node("pdfmonkey.list_documents")
async def pdfmonkey_list_documents(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all generated PDF documents.

    config:
      api_key     — PDFMonkey API key (required)
      page        — page number (optional, default 1)
      per_page    — results per page (optional, default 25)
      status      — filter by status: "pending", "generating", "success", "error" (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params: dict = {
        "page": merged.get("page", 1),
        "per_page": merged.get("per_page", 25),
    }
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=PDFMONKEY_BASE, timeout=30) as client:
        r = await client.get(
            "/documents", headers=_pdfmonkey_headers(api_key), params=params
        )
        r.raise_for_status()
        data = r.json()

    documents = data.get("documents", [])
    log.info("pdfmonkey.list_documents", count=len(documents))
    return {
        "documents": documents,
        "count": len(documents),
        "meta": data.get("meta", {}),
    }


@register_node("pdfmonkey.get_document")
async def pdfmonkey_get_document(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get details of a specific PDFMonkey document.

    config:
      api_key     — PDFMonkey API key (required)
      document_id — document ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    document_id = merged.get("document_id")
    if not document_id:
        raise ValueError("document_id is required for pdfmonkey.get_document")

    async with httpx.AsyncClient(base_url=PDFMONKEY_BASE, timeout=30) as client:
        r = await client.get(
            f"/documents/{document_id}", headers=_pdfmonkey_headers(api_key)
        )
        r.raise_for_status()
        data = r.json()

    document = data.get("document", data)
    log.info(
        "pdfmonkey.get_document",
        document_id=document_id,
        status=document.get("status"),
        download_url=document.get("download_url"),
    )
    return {"document": document, "document_id": document_id}


@register_node("pdfmonkey.delete_document")
async def pdfmonkey_delete_document(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Delete a PDFMonkey document.

    config:
      api_key     — PDFMonkey API key (required)
      document_id — document ID to delete (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    document_id = merged.get("document_id")
    if not document_id:
        raise ValueError("document_id is required for pdfmonkey.delete_document")

    async with httpx.AsyncClient(base_url=PDFMONKEY_BASE, timeout=30) as client:
        r = await client.delete(
            f"/documents/{document_id}", headers=_pdfmonkey_headers(api_key)
        )
        r.raise_for_status()

    log.info("pdfmonkey.delete_document", document_id=document_id)
    return {"success": True, "document_id": document_id}


@register_node("pdfmonkey.list_templates")
async def pdfmonkey_list_templates(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all PDF document templates in the PDFMonkey account.

    config:
      api_key  — PDFMonkey API key (required)
      page     — page number (optional, default 1)
      per_page — results per page (optional, default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params = {
        "page": merged.get("page", 1),
        "per_page": merged.get("per_page", 25),
    }

    async with httpx.AsyncClient(base_url=PDFMONKEY_BASE, timeout=30) as client:
        r = await client.get(
            "/document_templates", headers=_pdfmonkey_headers(api_key), params=params
        )
        r.raise_for_status()
        data = r.json()

    templates = data.get("document_templates", [])
    log.info("pdfmonkey.list_templates", count=len(templates))
    return {
        "templates": templates,
        "count": len(templates),
        "meta": data.get("meta", {}),
    }
