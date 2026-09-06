"""FileToPDF integration — convert files, HTML, and URLs to PDF via Gotenberg."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DEFAULT_GOTENBERG_URL = "http://localhost:3000"


def _gotenberg_base(config: dict) -> str:
    return config.get("gotenberg_url", DEFAULT_GOTENBERG_URL).rstrip("/")


@register_node("filetopdf.convert_file")
async def filetopdf_convert_file(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Convert a document file (DOCX, ODT, XLSX, PPTX, etc.) to PDF via Gotenberg/LibreOffice.

    config:
      gotenberg_url  — Gotenberg server URL (optional, default http://localhost:3000)
      file_content   — base64-encoded file content (required)
      filename       — filename with extension e.g. "document.docx" (required)
      landscape      — render in landscape orientation (optional, default False)
    """
    merged = {**config, **input_data}
    base_url = _gotenberg_base(merged)
    file_content_b64 = merged.get("file_content")
    filename = merged.get("filename")

    if not file_content_b64 or not filename:
        raise ValueError("file_content and filename are required for filetopdf.convert_file")

    import base64 as _b64
    file_bytes = _b64.b64decode(file_content_b64)

    files = {"files": (filename, file_bytes, "application/octet-stream")}
    data: dict = {}
    if merged.get("landscape"):
        data["landscape"] = "true"

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        r = await client.post(
            "/forms/libreoffice/convert",
            files=files,
            data=data,
        )
        r.raise_for_status()
        pdf_content = r.content

    log.info("filetopdf.convert_file", filename=filename, size=len(pdf_content))
    return {
        "filename": filename.rsplit(".", 1)[0] + ".pdf",
        "content_type": "application/pdf",
        "size": len(pdf_content),
        "content_hex": pdf_content.hex(),
    }


@register_node("filetopdf.html_to_pdf")
async def filetopdf_html_to_pdf(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Convert HTML content to PDF via Gotenberg/Chromium.

    config:
      gotenberg_url   — Gotenberg server URL (optional, default http://localhost:3000)
      html            — HTML string to convert (required)
      paper_width     — paper width in inches (optional, default 8.5)
      paper_height    — paper height in inches (optional, default 11)
      margin_top      — top margin in inches (optional, default 0.39)
      margin_bottom   — bottom margin in inches (optional, default 0.39)
      margin_left     — left margin in inches (optional, default 0.39)
      margin_right    — right margin in inches (optional, default 0.39)
      landscape       — render in landscape (optional, default False)
      print_background — print CSS background (optional, default True)
    """
    merged = {**config, **input_data}
    base_url = _gotenberg_base(merged)
    html = merged.get("html")

    if not html:
        raise ValueError("html is required for filetopdf.html_to_pdf")

    html_bytes = html.encode("utf-8") if isinstance(html, str) else html

    files = {"files": ("index.html", html_bytes, "text/html")}
    data = {
        "paperWidth": str(merged.get("paper_width", 8.5)),
        "paperHeight": str(merged.get("paper_height", 11)),
        "marginTop": str(merged.get("margin_top", 0.39)),
        "marginBottom": str(merged.get("margin_bottom", 0.39)),
        "marginLeft": str(merged.get("margin_left", 0.39)),
        "marginRight": str(merged.get("margin_right", 0.39)),
        "landscape": "true" if merged.get("landscape", False) else "false",
        "printBackground": "true" if merged.get("print_background", True) else "false",
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        r = await client.post(
            "/forms/chromium/convert/html",
            files=files,
            data=data,
        )
        r.raise_for_status()
        pdf_content = r.content

    log.info("filetopdf.html_to_pdf", size=len(pdf_content))
    return {
        "filename": "output.pdf",
        "content_type": "application/pdf",
        "size": len(pdf_content),
        "content_hex": pdf_content.hex(),
    }


@register_node("filetopdf.url_to_pdf")
async def filetopdf_url_to_pdf(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Convert a web URL to PDF via Gotenberg/Chromium.

    config:
      gotenberg_url   — Gotenberg server URL (optional, default http://localhost:3000)
      url             — URL of the page to convert (required)
      paper_width     — paper width in inches (optional, default 8.5)
      paper_height    — paper height in inches (optional, default 11)
      landscape       — render in landscape (optional, default False)
      print_background — print CSS background (optional, default True)
      wait_delay      — delay in duration format e.g. "1s" before rendering (optional)
    """
    merged = {**config, **input_data}
    base_url = _gotenberg_base(merged)
    url = merged.get("url")

    if not url:
        raise ValueError("url is required for filetopdf.url_to_pdf")

    data = {
        "url": url,
        "paperWidth": str(merged.get("paper_width", 8.5)),
        "paperHeight": str(merged.get("paper_height", 11)),
        "landscape": "true" if merged.get("landscape", False) else "false",
        "printBackground": "true" if merged.get("print_background", True) else "false",
    }
    if merged.get("wait_delay"):
        data["waitDelay"] = merged["wait_delay"]

    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        r = await client.post(
            "/forms/chromium/convert/url",
            data=data,
        )
        r.raise_for_status()
        pdf_content = r.content

    log.info("filetopdf.url_to_pdf", url=url, size=len(pdf_content))
    return {
        "url": url,
        "filename": "output.pdf",
        "content_type": "application/pdf",
        "size": len(pdf_content),
        "content_hex": pdf_content.hex(),
    }
