"""Instabase integration — document processing and automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return config.get("base_url", "https://instabase.com").rstrip("/")


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('access_token', '')}", "Content-Type": "application/json"}


@register_node("instabase.run_workflow")
async def instabase_run_workflow(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        r = await client.post(f"{_base(merged)}/api/v1/workflows/run", json={
            "workflow_id": merged.get("workflow_id", ""),
            "input": merged.get("input", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("instabase.get_job_status")
async def instabase_get_job_status(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    job_id = merged.get("job_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{_base(merged)}/api/v1/jobs/{job_id}")
        r.raise_for_status()
    return r.json()
