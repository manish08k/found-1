"""Zuora subscription billing platform — handler for zuora integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://rest.zuora.com/v1"


@register_node("zuora.list_accounts")
async def zuora_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List accounts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/accounts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zuora.list_accounts")
    return {"data": data}

@register_node("zuora.create_account")
async def zuora_create_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an account.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
      currency — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    currency = merged.get("currency") or ""
    if not name or not currency:
        raise ValueError("name, currency required for zuora.create_account")
    payload = {"name": name, "currency": currency}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/accounts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zuora.create_account")
    return {"data": data}

@register_node("zuora.list_subscriptions")
async def zuora_list_subscriptions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List subscriptions for an account.

    config/input_data:
      api_key — API key or token (required)
      account_key — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    account_key = merged.get("account_key") or ""
    if not account_key:
        raise ValueError("account_key required for zuora.list_subscriptions")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/subscriptions/accounts/{account_key}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("zuora.list_subscriptions")
    return {"data": data}

@register_node("zuora.create_subscription")
async def zuora_create_subscription(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a subscription.

    config/input_data:
      api_key — API key or token (required)
      accountKey — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    accountKey = merged.get("accountKey") or ""
    if not accountKey:
        raise ValueError("accountKey required for zuora.create_subscription")
    payload = {"accountKey": accountKey}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/subscriptions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("zuora.create_subscription")
    return {"data": data}
