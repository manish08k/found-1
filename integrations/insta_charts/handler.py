"""InstaCharts integration — chart and graph generation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.instacharts.io/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("insta_charts.create_chart")
async def insta_charts_create_chart(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/charts", json={
            "type": merged.get("chart_type", "bar"),
            "data": merged.get("data", {}),
            "options": merged.get("options", {}),
        })
        r.raise_for_status()
    return r.json()
