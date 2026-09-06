"""Barcode Lookup product data API — handler for barcode_lookup integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.barcodelookup.com/v3"


@register_node("barcode_lookup.lookup")
async def barcode_lookup_lookup(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Look up a product by barcode.

    config/input_data:
      api_key — API key or token (required)
      barcode — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Content-Type": "application/json"}
    # Auth passed as query param: key
    barcode = merged.get("barcode") or ""
    if not barcode:
        raise ValueError("barcode required for barcode_lookup.lookup")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/products", headers=headers, params={"key": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("barcode_lookup.lookup")
    return {"data": data}
