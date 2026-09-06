"""Metatext integration — no-code NLP and AI training."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://metatext.io/api/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("metatext.classify_text")
async def metatext_classify_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    dataset_id = merged.get("dataset_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/datasets/{dataset_id}/predict", json={"text": merged.get("text", "")})
        r.raise_for_status()
    return r.json()


@register_node("metatext.get_datasets")
async def metatext_get_datasets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/datasets")
        r.raise_for_status()
    return {"datasets": r.json()}
