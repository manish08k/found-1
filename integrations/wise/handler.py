"""Wise (TransferWise) integration — money transfers, profiles, balances, quotes."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

WISE_BASE = "https://api.wise.com"


def _wise_headers(api_token: str) -> dict:
    return {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}


@register_node("wise.list_profiles")
async def wise_list_profiles(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Wise user/business profiles for the authenticated account.

    config:
      api_token — Wise API bearer token (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")

    async with httpx.AsyncClient(base_url=WISE_BASE, timeout=30) as client:
        r = await client.get("/v1/profiles", headers=_wise_headers(api_token))
        r.raise_for_status()
        profiles = r.json()

    log.info("wise.list_profiles", count=len(profiles))
    return {"profiles": profiles, "count": len(profiles)}


@register_node("wise.get_balance")
async def wise_get_balance(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get STANDARD balances for a Wise profile.

    config:
      api_token  — Wise API bearer token (required)
      profile_id — Wise profile ID (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    profile_id = merged.get("profile_id")
    if not profile_id:
        raise ValueError("profile_id is required for wise.get_balance")

    async with httpx.AsyncClient(base_url=WISE_BASE, timeout=30) as client:
        r = await client.get(
            f"/v4/profiles/{profile_id}/balances",
            headers=_wise_headers(api_token),
            params={"types": "STANDARD"},
        )
        r.raise_for_status()
        balances = r.json()

    log.info("wise.get_balance", profile_id=profile_id, count=len(balances))
    return {"balances": balances, "profile_id": profile_id}


@register_node("wise.create_quote")
async def wise_create_quote(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a Wise transfer quote.

    config:
      api_token       — Wise API bearer token (required)
      profile_id      — Wise profile ID (required)
      source_currency — e.g. "GBP" (required)
      target_currency — e.g. "EUR" (required)
      source_amount   — amount in source currency (provide one of source/target)
      target_amount   — amount in target currency
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    profile_id = merged.get("profile_id")
    if not profile_id:
        raise ValueError("profile_id is required for wise.create_quote")

    payload: dict = {
        "sourceCurrency": merged.get("source_currency"),
        "targetCurrency": merged.get("target_currency"),
    }
    if merged.get("source_amount") is not None:
        payload["sourceAmount"] = merged["source_amount"]
    if merged.get("target_amount") is not None:
        payload["targetAmount"] = merged["target_amount"]

    async with httpx.AsyncClient(base_url=WISE_BASE, timeout=30) as client:
        r = await client.post(
            f"/v3/profiles/{profile_id}/quotes",
            headers=_wise_headers(api_token),
            json=payload,
        )
        r.raise_for_status()
        quote = r.json()

    log.info("wise.create_quote", profile_id=profile_id, quote_id=quote.get("id"))
    return {"quote": quote, "quote_id": quote.get("id")}


@register_node("wise.create_transfer")
async def wise_create_transfer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a Wise transfer.

    config:
      api_token                    — Wise API bearer token (required)
      target_account_id            — recipient account ID (required)
      quote_uuid                   — quote UUID from create_quote (required)
      customer_transaction_id      — optional idempotency UUID
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    target_account_id = merged.get("target_account_id")
    quote_uuid = merged.get("quote_uuid")
    if not target_account_id or not quote_uuid:
        raise ValueError("target_account_id and quote_uuid are required for wise.create_transfer")

    import uuid as _uuid
    payload: dict = {
        "targetAccount": target_account_id,
        "quoteUuid": quote_uuid,
        "customerTransactionId": merged.get("customer_transaction_id") or str(_uuid.uuid4()),
    }

    async with httpx.AsyncClient(base_url=WISE_BASE, timeout=30) as client:
        r = await client.post(
            "/v1/transfers",
            headers=_wise_headers(api_token),
            json=payload,
        )
        r.raise_for_status()
        transfer = r.json()

    log.info("wise.create_transfer", transfer_id=transfer.get("id"))
    return {"transfer": transfer, "transfer_id": transfer.get("id")}


@register_node("wise.fund_transfer")
async def wise_fund_transfer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fund a Wise transfer from the profile balance.

    config:
      api_token   — Wise API bearer token (required)
      profile_id  — Wise profile ID (required)
      transfer_id — transfer ID to fund (required)
      type        — funding type, default "BALANCE"
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    profile_id = merged.get("profile_id")
    transfer_id = merged.get("transfer_id")
    if not profile_id or not transfer_id:
        raise ValueError("profile_id and transfer_id are required for wise.fund_transfer")

    payload = {"type": merged.get("type", "BALANCE")}

    async with httpx.AsyncClient(base_url=WISE_BASE, timeout=30) as client:
        r = await client.post(
            f"/v3/profiles/{profile_id}/transfers/{transfer_id}/payments",
            headers=_wise_headers(api_token),
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("wise.fund_transfer", transfer_id=transfer_id, status=result.get("status"))
    return {"result": result, "transfer_id": transfer_id, "status": result.get("status")}


@register_node("wise.get_transfer")
async def wise_get_transfer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Wise transfer.

    config:
      api_token   — Wise API bearer token (required)
      transfer_id — transfer ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_token = merged.get("api_token", "")
    transfer_id = merged.get("transfer_id")
    if not transfer_id:
        raise ValueError("transfer_id is required for wise.get_transfer")

    async with httpx.AsyncClient(base_url=WISE_BASE, timeout=30) as client:
        r = await client.get(
            f"/v1/transfers/{transfer_id}",
            headers=_wise_headers(api_token),
        )
        r.raise_for_status()
        transfer = r.json()

    log.info("wise.get_transfer", transfer_id=transfer_id, status=transfer.get("status"))
    return {"transfer": transfer, "transfer_id": transfer_id, "status": transfer.get("status")}
