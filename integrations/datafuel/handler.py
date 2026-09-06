"""DataFuel integration — web data extraction."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.datafuel.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("datafuel.scrape_url")
async def datafuel_scrape_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/scrape", json={"url": merged.get("url", "")})
        r.raise_for_status()
    return r.json()


@register_node("datafuel.extract_data")
async def datafuel_extract_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{BASE}/extract", json={
            "url": merged.get("url", ""),
            "schema": merged.get("schema", {}),
        })
        r.raise_for_status()
    return r.json()
