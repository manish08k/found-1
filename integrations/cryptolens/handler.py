"""Cryptolens integration — software licensing."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://app.cryptolens.io/api"


def _headers(config: dict) -> dict:
    return {"Content-Type": "application/json"}


@register_node("cryptolens.activate_license")
async def cryptolens_activate_license(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/key/Activate", params={
            "token": merged.get("access_token", ""),
            "ProductId": merged.get("product_id", ""),
            "Key": merged.get("license_key", ""),
            "MachineCode": merged.get("machine_code", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("cryptolens.validate_license")
async def cryptolens_validate_license(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/key/Validate", params={
            "token": merged.get("access_token", ""),
            "ProductId": merged.get("product_id", ""),
            "Key": merged.get("license_key", ""),
            "MachineCode": merged.get("machine_code", ""),
        })
        r.raise_for_status()
    return r.json()
