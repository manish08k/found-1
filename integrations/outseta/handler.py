"""Outseta all-in-one SaaS platform integration — accounts and contacts."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _outseta_base(subdomain: str) -> str:
    return f"https://{subdomain}.outseta.com/api/v1"


@register_node("outseta.list_accounts")
async def outseta_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List accounts from Outseta.

    config/input_data:
      api_key    — Outseta API key (required)
      api_secret — Outseta API secret (required)
      subdomain  — Outseta account subdomain (required)
      limit      — maximum number of accounts to return (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    api_secret = merged.get("api_secret") or ""
    subdomain = merged.get("subdomain") or ""
    limit = int(merged.get("limit", 25))

    if not subdomain:
        raise ValueError("subdomain is required for outseta.list_accounts")

    headers = {"Authorization": f"Outseta {api_key}:{api_secret}"}
    url = f"{_outseta_base(subdomain)}/crm/accounts"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"fields": "*", "limit": limit})
        r.raise_for_status()
        data = r.json()

    accounts = data.get("items", data)
    log.info("outseta.list_accounts", subdomain=subdomain, count=len(accounts) if isinstance(accounts, list) else None)
    return {"accounts": accounts, "total": data.get("metadata", {}).get("total")}


@register_node("outseta.create_account")
async def outseta_create_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an account in Outseta.

    config/input_data:
      api_key    — Outseta API key (required)
      api_secret — Outseta API secret (required)
      subdomain  — Outseta account subdomain (required)
      name       — account/company name (required)
      email      — primary contact email (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    api_secret = merged.get("api_secret") or ""
    subdomain = merged.get("subdomain") or ""
    name = merged.get("name") or ""
    email = merged.get("email") or ""

    if not subdomain:
        raise ValueError("subdomain is required for outseta.create_account")
    if not name:
        raise ValueError("name is required for outseta.create_account")

    headers = {"Authorization": f"Outseta {api_key}:{api_secret}"}
    url = f"{_outseta_base(subdomain)}/crm/accounts"
    payload: dict = {"Name": name}
    if email:
        payload["PersonAccount"] = {"Email": email}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("outseta.create_account", name=name, uid=data.get("Uid"))
    return {"account": data}


@register_node("outseta.list_contacts")
async def outseta_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts (people) from Outseta.

    config/input_data:
      api_key    — Outseta API key (required)
      api_secret — Outseta API secret (required)
      subdomain  — Outseta account subdomain (required)
      limit      — maximum number of contacts to return (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    api_secret = merged.get("api_secret") or ""
    subdomain = merged.get("subdomain") or ""
    limit = int(merged.get("limit", 25))

    if not subdomain:
        raise ValueError("subdomain is required for outseta.list_contacts")

    headers = {"Authorization": f"Outseta {api_key}:{api_secret}"}
    url = f"{_outseta_base(subdomain)}/crm/people"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"fields": "*", "limit": limit})
        r.raise_for_status()
        data = r.json()

    contacts = data.get("items", data)
    log.info("outseta.list_contacts", subdomain=subdomain, count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts, "total": data.get("metadata", {}).get("total")}
