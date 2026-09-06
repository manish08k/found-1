"""PDF4me document conversion and manipulation integration."""
import base64
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERVICE_BASE = "https://api.pdf4me.com"


def _auth_header(api_key: str) -> str:
    token = base64.b64encode(f"{api_key}:".encode()).decode()
    return f"Basic {token}"


@register_node("pdf4me.convert_to_pdf")
async def pdf4me_convert_to_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert a document to PDF using PDF4me."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf4me.convert_to_pdf")
    doc_content = merged.get("doc_content", "")
    doc_name = merged.get("doc_name", "document.docx")
    if not doc_content:
        raise ValueError("doc_content is required for pdf4me.convert_to_pdf")
    payload = {
        "docContent": doc_content,
        "docName": doc_name,
        "async": False,
    }
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post(
            "/Convert/ConvertToPdf",
            headers={"Authorization": _auth_header(api_key)},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    log.info("pdf4me.convert_to_pdf", doc_name=doc_name)
    return {"result": data, "pdf_content": data.get("docContent", "")}


@register_node("pdf4me.merge_pdf")
async def pdf4me_merge_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Merge multiple PDFs using PDF4me."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf4me.merge_pdf")
    docs = merged.get("docs", [])
    if not docs:
        raise ValueError("docs is required for pdf4me.merge_pdf")
    payload = {"docs": docs, "async": False}
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post(
            "/Merge/Merge",
            headers={"Authorization": _auth_header(api_key)},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    log.info("pdf4me.merge_pdf", count=len(docs))
    return {"result": data, "pdf_content": data.get("docContent", "")}


@register_node("pdf4me.split_pdf")
async def pdf4me_split_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Split a PDF using PDF4me."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf4me.split_pdf")
    doc_content = merged.get("doc_content", "")
    split_after_pages = merged.get("split_after_pages", [])
    if not doc_content:
        raise ValueError("doc_content is required for pdf4me.split_pdf")
    payload = {
        "docContent": doc_content,
        "docName": merged.get("doc_name", "document.pdf"),
        "splitAfterPages": split_after_pages,
        "async": False,
    }
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post(
            "/Split/SplitByPageNr",
            headers={"Authorization": _auth_header(api_key)},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    log.info("pdf4me.split_pdf")
    return {"result": data, "docs": data.get("docs", [])}


@register_node("pdf4me.compress_pdf")
async def pdf4me_compress_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Compress a PDF using PDF4me."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf4me.compress_pdf")
    doc_content = merged.get("doc_content", "")
    if not doc_content:
        raise ValueError("doc_content is required for pdf4me.compress_pdf")
    payload = {
        "docContent": doc_content,
        "docName": merged.get("doc_name", "document.pdf"),
        "async": False,
    }
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post(
            "/Optimize/Optimize",
            headers={"Authorization": _auth_header(api_key)},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    log.info("pdf4me.compress_pdf")
    return {"result": data, "pdf_content": data.get("docContent", "")}
