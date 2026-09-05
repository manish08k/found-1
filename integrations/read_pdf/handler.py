"""ReadPdf integration — extract text and metadata from PDF files.

No credentials required.
Nodes:
  - read_pdf.extract_text  : extract full text from a PDF
  - read_pdf.get_metadata  : return PDF document metadata
"""
import base64
import io
import structlog
import httpx  # noqa: F401 — standard import kept for consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Library import with fallback
# ---------------------------------------------------------------------------
try:
    import pypdf as _pdf_lib  # type: ignore

    def _open_reader(data: bytes):
        return _pdf_lib.PdfReader(io.BytesIO(data))

    _PDF_BACKEND = "pypdf"
except ImportError:
    try:
        import PyPDF2 as _pdf_lib  # type: ignore

        def _open_reader(data: bytes):
            return _pdf_lib.PdfReader(io.BytesIO(data))

        _PDF_BACKEND = "PyPDF2"
    except ImportError:
        _pdf_lib = None  # type: ignore
        _PDF_BACKEND = None

        def _open_reader(data: bytes):
            raise RuntimeError(
                "No PDF library found. Install 'pypdf' or 'PyPDF2': pip install pypdf"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_pdf_bytes(config: dict, input_data: dict) -> bytes:
    """Return raw PDF bytes from file_path or file_base64."""
    file_path = config.get("file_path") or input_data.get("file_path")
    file_base64 = config.get("file_base64") or input_data.get("file_base64")

    if file_base64:
        return base64.b64decode(file_base64)
    if file_path:
        with open(file_path, "rb") as fh:
            return fh.read()
    raise ValueError("Either 'file_path' or 'file_base64' must be provided")


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("read_pdf.extract_text")
async def extract_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Extract all text from a PDF file, page by page."""
    log.info("read_pdf.extract_text", backend=_PDF_BACKEND)
    pdf_bytes = await _load_pdf_bytes(config, input_data)
    reader = _open_reader(pdf_bytes)

    pages = []
    full_text_parts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append({"page": i + 1, "text": text})
        full_text_parts.append(text)

    full_text = "\n".join(full_text_parts)
    log.info("read_pdf.extract_text.done", pages=len(pages), chars=len(full_text))
    return {
        "text": full_text,
        "pages": pages,
        "page_count": len(pages),
        "backend": _PDF_BACKEND,
    }


@register_node("read_pdf.get_metadata")
async def get_metadata(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return PDF document metadata (author, title, creation date, etc.)."""
    log.info("read_pdf.get_metadata", backend=_PDF_BACKEND)
    pdf_bytes = await _load_pdf_bytes(config, input_data)
    reader = _open_reader(pdf_bytes)

    meta = reader.metadata or {}
    # Normalise: pypdf and PyPDF2 both expose metadata as a mapping-like object
    metadata = {k.lstrip("/"): str(v) for k, v in meta.items()}

    result = {
        "metadata": metadata,
        "page_count": len(reader.pages),
        "backend": _PDF_BACKEND,
    }
    log.info("read_pdf.get_metadata.done", fields=list(metadata.keys()))
    return result
