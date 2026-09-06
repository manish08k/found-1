"""eSignatures integration — electronic signature collection."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://esignatures.io/api"


def _headers(config: dict) -> dict:
    return {"Content-Type": "application/json"}


def _params(config: dict) -> dict:
    return {"token": config.get("api_token", "")}


@register_node("esignatures.send_contract")
async def esignatures_send_contract(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE}/contracts", params=_params(merged), json={
            "template_id": merged.get("template_id", ""),
            "signers": merged.get("signers", []),
            "placeholder_fields": merged.get("placeholder_fields", []),
        })
        r.raise_for_status()
    return r.json()


@register_node("esignatures.get_contract")
async def esignatures_get_contract(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    contract_id = merged.get("contract_id", "")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE}/contracts/{contract_id}", params=_params(merged))
        r.raise_for_status()
    return r.json()
