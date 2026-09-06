"""PDFCrowd integration — HTML to PDF conversion."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.pdfcrowd.com/convert/21.10"


@register_node("pdfcrowd.html_to_pdf")
async def pdfcrowd_html_to_pdf(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    username = merged.get("username", "")
    api_key = merged.get("api_key", "")
    async with httpx.AsyncClient(auth=(username, api_key), timeout=60) as client:
        data = {"output_format": "pdf"}
        if merged.get("url"):
            data["url"] = merged.get("url")
        elif merged.get("html"):
            data["html"] = merged.get("html")
        r = await client.post(f"{BASE}/html/", data=data)
        r.raise_for_status()
    import base64
    return {"pdf_base64": base64.b64encode(r.content).decode(), "size_bytes": len(r.content)}


@register_node("pdfcrowd.url_to_pdf")
async def pdfcrowd_url_to_pdf(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    import base64
    async with httpx.AsyncClient(auth=(merged.get("username", ""), merged.get("api_key", "")), timeout=60) as client:
        r = await client.post(f"{BASE}/url/", data={"url": merged.get("url", ""), "output_format": "pdf"})
        r.raise_for_status()
    return {"pdf_base64": base64.b64encode(r.content).decode(), "size_bytes": len(r.content)}
