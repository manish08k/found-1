"""EditionGuard integration — eBook DRM and digital publishing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://editionguard.com/api/v1"


def _headers(config: dict) -> dict:
    return {"X-API-Key": config.get("api_key", ""), "Content-Type": "application/json"}


@register_node("editionguard.create_download_link")
async def editionguard_create_download_link(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/download-links", json={
            "book_id": merged.get("book_id", ""),
            "customer_email": merged.get("customer_email", ""),
            "customer_name": merged.get("customer_name", ""),
        })
        r.raise_for_status()
    return r.json()
