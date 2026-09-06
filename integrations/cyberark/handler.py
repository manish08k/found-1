"""CyberArk Privileged Access Manager integration — accounts and credentials."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _cyberark_base(base_url: str) -> str:
    return f"https://{base_url}/PasswordVault/api"


def _cyberark_headers(auth_token: str) -> dict:
    return {
        "Authorization": f"CyberArk {auth_token}",
        "Content-Type": "application/json",
    }


@register_node("cyberark.list_accounts")
async def cyberark_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List accounts in the CyberArk vault.

    config:
      base_url   — CyberArk server hostname (required)
      auth_token — CyberArk session token from logon (required)
      search     — search term (optional)
      safe_name  — filter by safe name (optional)
      limit      — number of records to return (optional, default 50)
      offset     — offset for pagination (optional, default 0)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    auth_token = merged.get("auth_token", "")
    if not base_url or not auth_token:
        raise ValueError("base_url and auth_token are required for cyberark.list_accounts")

    params: dict = {"limit": merged.get("limit", 50), "offset": merged.get("offset", 0)}
    if merged.get("search"):
        params["search"] = merged["search"]
    if merged.get("safe_name"):
        params["safeName"] = merged["safe_name"]

    async with httpx.AsyncClient(base_url=_cyberark_base(base_url), timeout=30) as client:
        r = await client.get("/Accounts", headers=_cyberark_headers(auth_token), params=params)
        r.raise_for_status()
        data = r.json()

    accounts = data.get("value", [])
    log.info("cyberark.list_accounts", count=len(accounts))
    return {"accounts": accounts, "count": data.get("count", len(accounts))}


@register_node("cyberark.get_account")
async def cyberark_get_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific CyberArk account.

    config:
      base_url   — CyberArk server hostname (required)
      auth_token — CyberArk session token (required)
      account_id — account ID to retrieve (required)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    auth_token = merged.get("auth_token", "")
    account_id = merged.get("account_id")
    if not base_url or not auth_token or not account_id:
        raise ValueError("base_url, auth_token, and account_id are required")

    async with httpx.AsyncClient(base_url=_cyberark_base(base_url), timeout=30) as client:
        r = await client.get(f"/Accounts/{account_id}", headers=_cyberark_headers(auth_token))
        r.raise_for_status()
        account = r.json()

    log.info("cyberark.get_account", account_id=account_id)
    return {"account": account, "account_id": account_id}


@register_node("cyberark.get_password")
async def cyberark_get_password(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve the password value for a CyberArk account.

    config:
      base_url   — CyberArk server hostname (required)
      auth_token — CyberArk session token (required)
      account_id — account ID whose password to retrieve (required)
      reason     — reason for retrieval (optional)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    auth_token = merged.get("auth_token", "")
    account_id = merged.get("account_id")
    if not base_url or not auth_token or not account_id:
        raise ValueError("base_url, auth_token, and account_id are required")

    payload: dict = {}
    if merged.get("reason"):
        payload["reason"] = merged["reason"]

    async with httpx.AsyncClient(base_url=_cyberark_base(base_url), timeout=30) as client:
        r = await client.post(
            f"/Accounts/{account_id}/Password/Retrieve",
            headers=_cyberark_headers(auth_token),
            json=payload,
        )
        r.raise_for_status()
        password = r.text.strip('"')

    log.info("cyberark.get_password", account_id=account_id)
    return {"password": password, "account_id": account_id}


@register_node("cyberark.add_account")
async def cyberark_add_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a new account to the CyberArk vault.

    config:
      base_url        — CyberArk server hostname (required)
      auth_token      — CyberArk session token (required)
      safe_name       — safe to add account to (required)
      platform_id     — platform ID (required)
      name            — account name (optional)
      address         — target system address (optional)
      user_name       — account username (optional)
      secret_type     — secret type e.g. "password" (optional)
      secret          — initial secret value (optional)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    auth_token = merged.get("auth_token", "")
    safe_name = merged.get("safe_name")
    platform_id = merged.get("platform_id")
    if not base_url or not auth_token or not safe_name or not platform_id:
        raise ValueError("base_url, auth_token, safe_name, and platform_id are required")

    payload: dict = {"safeName": safe_name, "platformId": platform_id}
    for field in ["name", "address", "userName", "secretType", "secret"]:
        config_key = field.replace("N", "_n").replace("T", "_t").lower()
        if merged.get(config_key):
            payload[field] = merged[config_key]
    if merged.get("user_name"):
        payload["userName"] = merged["user_name"]
    if merged.get("secret_type"):
        payload["secretType"] = merged["secret_type"]
    if merged.get("secret"):
        payload["secret"] = merged["secret"]

    async with httpx.AsyncClient(base_url=_cyberark_base(base_url), timeout=30) as client:
        r = await client.post("/Accounts", headers=_cyberark_headers(auth_token), json=payload)
        r.raise_for_status()
        account = r.json()

    account_id = account.get("id")
    log.info("cyberark.add_account", account_id=account_id)
    return {"account": account, "account_id": account_id}


@register_node("cyberark.update_account")
async def cyberark_update_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing CyberArk account using PATCH operations.

    config:
      base_url   — CyberArk server hostname (required)
      auth_token — CyberArk session token (required)
      account_id — account ID to update (required)
      operations — list of JSON Patch operations [{op, path, value}] (required)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "")
    auth_token = merged.get("auth_token", "")
    account_id = merged.get("account_id")
    operations = merged.get("operations", [])
    if not base_url or not auth_token or not account_id:
        raise ValueError("base_url, auth_token, and account_id are required")

    async with httpx.AsyncClient(base_url=_cyberark_base(base_url), timeout=30) as client:
        r = await client.patch(
            f"/Accounts/{account_id}",
            headers=_cyberark_headers(auth_token),
            json=operations,
        )
        r.raise_for_status()
        account = r.json()

    log.info("cyberark.update_account", account_id=account_id)
    return {"account": account, "account_id": account_id}
