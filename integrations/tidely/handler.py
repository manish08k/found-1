"""Tidely integration — cash flow management for businesses."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.tidely.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("tidely.get_cash_flow")
async def tidely_get_cash_flow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/cashflow", params={"from": merged.get("from_date", ""), "to": merged.get("to_date", "")})
        r.raise_for_status()
    return r.json()


@register_node("tidely.get_scenarios")
async def tidely_get_scenarios(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/scenarios")
        r.raise_for_status()
    return {"scenarios": r.json()}
