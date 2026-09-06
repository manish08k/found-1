"""UseInbox email warm-up and deliverability — handler for useinbox integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.useinbox.com/v1"


@register_node("useinbox.list_accounts")
async def useinbox_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List email accounts.

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
    log.info("useinbox.list_accounts")
    return {"data": data}

@register_node("useinbox.add_account")
async def useinbox_add_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add an email account.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
      password — (required)
      smtp_host — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    email = merged.get("email") or ""
    password = merged.get("password") or ""
    smtp_host = merged.get("smtp_host") or ""
    if not email or not password or not smtp_host:
        raise ValueError("email, password, smtp_host required for useinbox.add_account")
    payload = {"email": email, "password": password, "smtp_host": smtp_host}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/accounts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("useinbox.add_account")
    return {"data": data}

@register_node("useinbox.get_stats")
async def useinbox_get_stats(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get account stats.

    config/input_data:
      api_key — API key or token (required)
      account_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    account_id = merged.get("account_id") or ""
    if not account_id:
        raise ValueError("account_id required for useinbox.get_stats")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/accounts/{account_id}/stats", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("useinbox.get_stats")
    return {"data": data}
