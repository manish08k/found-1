"""Mempool.space integration — Bitcoin blockchain explorer."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MEMPOOL_BASE = "https://mempool.space/api"


@register_node("mempool_space.get_address")
async def mempool_get_address(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get information about a Bitcoin address.

    config/input_data:
      address — Bitcoin address (required)
    """
    address = config.get("address") or input_data.get("address")
    if not address:
        raise ValueError("address is required for mempool_space.get_address")

    async with httpx.AsyncClient(base_url=MEMPOOL_BASE, timeout=30) as client:
        r = await client.get(f"/address/{address}")
        r.raise_for_status()
        data = r.json()

    log.info("mempool_space.get_address", address=address, tx_count=data.get("chain_stats", {}).get("tx_count"))
    return {
        "address": address,
        "chain_stats": data.get("chain_stats", {}),
        "mempool_stats": data.get("mempool_stats", {}),
        "raw": data,
    }


@register_node("mempool_space.get_transaction")
async def mempool_get_transaction(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a Bitcoin transaction by txid.

    config/input_data:
      txid — Transaction ID (required)
    """
    txid = config.get("txid") or input_data.get("txid")
    if not txid:
        raise ValueError("txid is required for mempool_space.get_transaction")

    async with httpx.AsyncClient(base_url=MEMPOOL_BASE, timeout=30) as client:
        r = await client.get(f"/tx/{txid}")
        r.raise_for_status()
        tx = r.json()

    log.info("mempool_space.get_transaction", txid=txid, confirmed=tx.get("status", {}).get("confirmed"))
    return {
        "txid": txid,
        "transaction": tx,
        "confirmed": tx.get("status", {}).get("confirmed"),
        "block_height": tx.get("status", {}).get("block_height"),
        "fee": tx.get("fee"),
    }


@register_node("mempool_space.get_fees")
async def mempool_get_fees(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get recommended Bitcoin transaction fees.

    No configuration required.
    """
    async with httpx.AsyncClient(base_url=MEMPOOL_BASE, timeout=30) as client:
        r = await client.get("/v1/fees/recommended")
        r.raise_for_status()
        fees = r.json()

    log.info("mempool_space.get_fees", fastest=fees.get("fastestFee"), economy=fees.get("economyFee"))
    return {
        "fastest_fee": fees.get("fastestFee"),
        "half_hour_fee": fees.get("halfHourFee"),
        "hour_fee": fees.get("hourFee"),
        "economy_fee": fees.get("economyFee"),
        "minimum_fee": fees.get("minimumFee"),
        "raw": fees,
    }


@register_node("mempool_space.get_block")
async def mempool_get_block(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a Bitcoin block by hash.

    config/input_data:
      hash — Block hash (required)
    """
    block_hash = config.get("hash") or input_data.get("hash")
    if not block_hash:
        raise ValueError("hash is required for mempool_space.get_block")

    async with httpx.AsyncClient(base_url=MEMPOOL_BASE, timeout=30) as client:
        r = await client.get(f"/block/{block_hash}")
        r.raise_for_status()
        block = r.json()

    log.info("mempool_space.get_block", hash=block_hash, height=block.get("height"), tx_count=block.get("tx_count"))
    return {
        "hash": block_hash,
        "block": block,
        "height": block.get("height"),
        "tx_count": block.get("tx_count"),
        "timestamp": block.get("timestamp"),
        "size": block.get("size"),
    }
