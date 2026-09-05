"""TrueLayer integration — open banking accounts, balances, and transactions."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TRUELAYER_BASE = "https://api.truelayer.com"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("truelayer.list_accounts")
async def truelayer_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all bank accounts connected via TrueLayer.

    config:
      access_token — TrueLayer OAuth access token (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for truelayer.list_accounts")

    async with httpx.AsyncClient(base_url=TRUELAYER_BASE, timeout=30) as client:
        r = await client.get("/data/v1/accounts", headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    accounts = data.get("results", [])
    log.info("truelayer.list_accounts", count=len(accounts))
    return {"accounts": accounts, "count": len(accounts), "status": data.get("status")}


@register_node("truelayer.get_balance")
async def truelayer_get_balance(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the balance for a specific account.

    config/input_data:
      access_token — TrueLayer OAuth access token (required)
      account_id   — Account ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    account_id = config.get("account_id") or input_data.get("account_id")

    if not access_token:
        raise ValueError("access_token is required for truelayer.get_balance")
    if not account_id:
        raise ValueError("account_id is required for truelayer.get_balance")

    async with httpx.AsyncClient(base_url=TRUELAYER_BASE, timeout=30) as client:
        r = await client.get(f"/data/v1/accounts/{account_id}/balance", headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    balance = data.get("results", [{}])[0] if data.get("results") else {}
    log.info("truelayer.get_balance", account_id=account_id, currency=balance.get("currency"))
    return {"balance": balance, "account_id": account_id, "current": balance.get("current"), "available": balance.get("available"), "currency": balance.get("currency")}


@register_node("truelayer.get_transactions")
async def truelayer_get_transactions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get transactions for a specific account.

    config/input_data:
      access_token — TrueLayer OAuth access token (required)
      account_id   — Account ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    account_id = config.get("account_id") or input_data.get("account_id")

    if not access_token:
        raise ValueError("access_token is required for truelayer.get_transactions")
    if not account_id:
        raise ValueError("account_id is required for truelayer.get_transactions")

    async with httpx.AsyncClient(base_url=TRUELAYER_BASE, timeout=30) as client:
        r = await client.get(f"/data/v1/accounts/{account_id}/transactions", headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    transactions = data.get("results", [])
    log.info("truelayer.get_transactions", account_id=account_id, count=len(transactions))
    return {"transactions": transactions, "account_id": account_id, "count": len(transactions)}
