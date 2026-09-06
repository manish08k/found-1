"""IBM Cognos integration — business intelligence and analytics."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return config.get("base_url", "").rstrip("/")


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('access_token', '')}", "Content-Type": "application/json"}


@register_node("ibm_cognose.run_report")
async def ibm_cognose_run_report(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    report_id = merged.get("report_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{_base(merged)}/api/v1/reports/{report_id}/run", json={
            "format": merged.get("format", "JSON"),
            "parameters": merged.get("parameters", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("ibm_cognose.get_reports")
async def ibm_cognose_get_reports(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{_base(merged)}/api/v1/reports")
        r.raise_for_status()
    return {"reports": r.json()}
