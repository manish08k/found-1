"""Ethereum Name Service (ENS) integration — resolve and lookup ENS names."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ENS_BASE = "https://api.ensideas.com/ens"


@register_node("eth_name_service.resolve_name")
async def ens_resolve_name(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Resolve an ENS name to an Ethereum address.

    config/input_data:
      name — ENS name e.g. "vitalik.eth" (required)
    """
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("name is required for eth_name_service.resolve_name")

    async with httpx.AsyncClient(base_url=ENS_BASE, timeout=30) as client:
        r = await client.get(f"/resolve/{name}")
        r.raise_for_status()
        data = r.json()

    address = data.get("address") or data.get("result")
    log.info("eth_name_service.resolve_name", name=name, address=address)
    return {"name": name, "address": address, "raw": data}


@register_node("eth_name_service.lookup_address")
async def ens_lookup_address(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Reverse lookup an Ethereum address to its ENS name.

    config/input_data:
      address — Ethereum address (required)
    """
    address = config.get("address") or input_data.get("address")
    if not address:
        raise ValueError("address is required for eth_name_service.lookup_address")

    async with httpx.AsyncClient(base_url=ENS_BASE, timeout=30) as client:
        r = await client.get(f"/lookup/{address}")
        r.raise_for_status()
        data = r.json()

    name = data.get("name") or data.get("result")
    log.info("eth_name_service.lookup_address", address=address, name=name)
    return {"address": address, "name": name, "raw": data}
