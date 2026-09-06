"""Blockscout blockchain explorer — handler for blockscout integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://eth.blockscout.com/api/v2"


@register_node("blockscout.get_address")
async def blockscout_get_address(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get address info.

    config/input_data:
      address — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    address = merged.get("address") or ""
    if not address:
        raise ValueError("address required for blockscout.get_address")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/addresses/{address}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("blockscout.get_address")
    return {"data": data}

@register_node("blockscout.get_transaction")
async def blockscout_get_transaction(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get transaction details.

    config/input_data:
      tx_hash — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    tx_hash = merged.get("tx_hash") or ""
    if not tx_hash:
        raise ValueError("tx_hash required for blockscout.get_transaction")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/transactions/{tx_hash}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("blockscout.get_transaction")
    return {"data": data}

@register_node("blockscout.list_transactions")
async def blockscout_list_transactions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List address transactions.

    config/input_data:
      address — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    address = merged.get("address") or ""
    if not address:
        raise ValueError("address required for blockscout.list_transactions")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/addresses/{address}/transactions", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("blockscout.list_transactions")
    return {"data": data}
