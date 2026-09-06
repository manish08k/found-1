"""Avian data analytics platform — handler for avian integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.avian.io/v1"


@register_node("avian.query")
async def avian_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run an analytics query.

    config/input_data:
      api_key — API key or token (required)
      query — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    query = merged.get("query") or ""
    if not query:
        raise ValueError("query required for avian.query")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/query", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("avian.query")
    return {"data": data}

@register_node("avian.list_datasets")
async def avian_list_datasets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List datasets.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/datasets", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("avian.list_datasets")
    return {"data": data}

@register_node("avian.get_dataset")
async def avian_get_dataset(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get dataset info.

    config/input_data:
      api_key — API key or token (required)
      dataset_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    dataset_id = merged.get("dataset_id") or ""
    if not dataset_id:
        raise ValueError("dataset_id required for avian.get_dataset")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/datasets/{dataset_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("avian.get_dataset")
    return {"data": data}
