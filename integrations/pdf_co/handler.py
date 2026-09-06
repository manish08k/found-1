"""PDF.co document conversion and manipulation integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERVICE_BASE = "https://api.pdf.co/v1"


@register_node("pdf_co.convert_to_pdf")
async def pdf_co_convert_to_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert a document to PDF using PDF.co."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf_co.convert_to_pdf")
    url = merged.get("url", "")
    if not url:
        raise ValueError("url is required for pdf_co.convert_to_pdf")
    payload = {"url": url}
    if merged.get("name"):
        payload["name"] = merged["name"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post("/pdf/convert/from/url", headers={"x-api-key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("pdf_co.convert_to_pdf", url=url)
    return {"result": data, "pdf_url": data.get("url", "")}


@register_node("pdf_co.convert_from_pdf")
async def pdf_co_convert_from_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert PDF to another format using PDF.co."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf_co.convert_from_pdf")
    url = merged.get("url", "")
    output_format = merged.get("output_format", "docx")
    if not url:
        raise ValueError("url is required for pdf_co.convert_from_pdf")
    payload = {"url": url}
    if merged.get("name"):
        payload["name"] = merged["name"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post(f"/pdf/convert/to/{output_format}", headers={"x-api-key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("pdf_co.convert_from_pdf", url=url, output_format=output_format)
    return {"result": data, "output_url": data.get("url", "")}


@register_node("pdf_co.merge_pdf")
async def pdf_co_merge_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Merge multiple PDFs using PDF.co."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf_co.merge_pdf")
    urls = merged.get("urls", [])
    if not urls:
        raise ValueError("urls is required for pdf_co.merge_pdf")
    payload = {"url": ",".join(urls) if isinstance(urls, list) else urls}
    if merged.get("name"):
        payload["name"] = merged["name"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post("/pdf/merge", headers={"x-api-key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("pdf_co.merge_pdf", count=len(urls))
    return {"result": data, "pdf_url": data.get("url", "")}


@register_node("pdf_co.split_pdf")
async def pdf_co_split_pdf(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Split a PDF using PDF.co."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf_co.split_pdf")
    url = merged.get("url", "")
    if not url:
        raise ValueError("url is required for pdf_co.split_pdf")
    payload = {"url": url}
    if merged.get("pages"):
        payload["pages"] = merged["pages"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post("/pdf/split", headers={"x-api-key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("pdf_co.split_pdf", url=url)
    return {"result": data, "urls": data.get("urls", [])}


@register_node("pdf_co.extract_text")
async def pdf_co_extract_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Extract text from a PDF using PDF.co."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for pdf_co.extract_text")
    url = merged.get("url", "")
    if not url:
        raise ValueError("url is required for pdf_co.extract_text")
    payload = {"url": url}
    if merged.get("pages"):
        payload["pages"] = merged["pages"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=60) as client:
        r = await client.post("/pdf/convert/to/text", headers={"x-api-key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("pdf_co.extract_text", url=url)
    return {"text": data.get("body", ""), "result": data}
