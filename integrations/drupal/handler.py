"""Drupal integration — CMS content management via JSON:API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return config.get("base_url", "").rstrip("/")


def _headers(config: dict) -> dict:
    return {
        "Authorization": f"Bearer {config.get('access_token', '')}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }


@register_node("drupal.get_node")
async def drupal_get_node(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    node_type = merged.get("node_type", "article")
    node_id = merged.get("node_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{_base(merged)}/jsonapi/node/{node_type}/{node_id}")
        r.raise_for_status()
    return r.json()


@register_node("drupal.create_node")
async def drupal_create_node(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    node_type = merged.get("node_type", "article")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/jsonapi/node/{node_type}", json={
            "data": {"type": f"node--{node_type}", "attributes": merged.get("attributes", {})}
        })
        r.raise_for_status()
    return r.json()


@register_node("drupal.update_node")
async def drupal_update_node(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    node_type = merged.get("node_type", "article")
    node_id = merged.get("node_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.patch(f"{_base(merged)}/jsonapi/node/{node_type}/{node_id}", json={
            "data": {"type": f"node--{node_type}", "id": node_id, "attributes": merged.get("attributes", {})}
        })
        r.raise_for_status()
    return r.json()
