"""JungleGrid integration — Amazon market research and analytics."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.junglegrid.net/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("jungle_grid.search_products")
async def jungle_grid_search_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/products/search", params={"q": merged.get("query", ""), "marketplace": merged.get("marketplace", "US")})
        r.raise_for_status()
    return {"products": r.json()}


@register_node("jungle_grid.get_product_details")
async def jungle_grid_get_product_details(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    asin = merged.get("asin", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/products/{asin}")
        r.raise_for_status()
    return r.json()
