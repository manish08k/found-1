"""iLoveAPI integration — document conversion and manipulation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.ilovepdf.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('public_key', '')}", "Content-Type": "application/json"}


@register_node("iloveapi.convert_pdf")
async def iloveapi_convert_pdf(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        # Start task
        task_r = await client.get(f"{BASE}/start/pdfjpg")
        task_r.raise_for_status()
        task_data = task_r.json()
        return {"task_id": task_data.get("task"), "server": task_data.get("server"), "status": "started"}


@register_node("iloveapi.compress_pdf")
async def iloveapi_compress_pdf(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=60) as client:
        task_r = await client.get(f"{BASE}/start/compress")
        task_r.raise_for_status()
        task_data = task_r.json()
        return {"task_id": task_data.get("task"), "server": task_data.get("server"), "status": "started"}
