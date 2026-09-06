"""SeekTable integration — business intelligence and reporting."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://www.seektable.com/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("seek_table.get_reports")
async def seek_table_get_reports(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/reports")
        r.raise_for_status()
    return {"reports": r.json()}


@register_node("seek_table.run_report")
async def seek_table_run_report(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    report_id = merged.get("report_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.get(f"{BASE}/report/{report_id}/data", params={"format": merged.get("format", "json")})
        r.raise_for_status()
    return {"data": r.json()}
