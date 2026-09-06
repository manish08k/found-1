"""Presentation integration — presentation generation utilities."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("presentation.create_slide")
async def presentation_create_slide(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {
        "slide_id": f"slide_{merged.get('index', 1)}",
        "title": merged.get("title", ""),
        "content": merged.get("content", ""),
        "layout": merged.get("layout", "default"),
    }


@register_node("presentation.export_to_pdf")
async def presentation_export_to_pdf(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {
        "presentation_id": merged.get("presentation_id", ""),
        "format": "pdf",
        "status": "exported",
        "url": merged.get("download_url", ""),
    }
