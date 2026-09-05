"""Klenty sales automation integration — prospects and cadences."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

KLENTY_BASE = "https://app.klenty.com/apis/v1/user"


@register_node("klenty.add_prospect")
async def klenty_add_prospect(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a new prospect to Klenty.

    config/input_data:
      api_key    — Klenty API key (required)
      first_name — prospect first name (required)
      last_name  — prospect last name
      email      — prospect email (required)
      phone      — phone number
      company    — company name
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""
    phone = merged.get("phone") or ""
    company = merged.get("company") or ""

    if not fn:
        raise ValueError("first_name is required for klenty.add_prospect")
    if not email:
        raise ValueError("email is required for klenty.add_prospect")

    headers = {"x-API-Key": api_key}
    url = f"{KLENTY_BASE}/prospect/create"
    payload = {
        "firstName": fn,
        "lastName": ln,
        "email": email,
        "phone": phone,
        "company": company,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("klenty.add_prospect", email=email)
    return {"prospect": data}


@register_node("klenty.list_prospects")
async def klenty_list_prospects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List prospects from Klenty.

    config/input_data:
      api_key — Klenty API key (required)
      page    — page number (default 1)
      size    — page size (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    page = int(merged.get("page", 1))
    size = int(merged.get("size", 25))

    headers = {"x-API-Key": api_key}
    url = f"{KLENTY_BASE}/prospect/all"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"Page": page, "Size": size})
        r.raise_for_status()
        data = r.json()

    prospects = data.get("data", data)
    log.info("klenty.list_prospects", page=page, count=len(prospects) if isinstance(prospects, list) else None)
    return {"prospects": prospects, "page": page}


@register_node("klenty.start_cadence")
async def klenty_start_cadence(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Start a cadence for a prospect in Klenty.

    config/input_data:
      api_key      — Klenty API key (required)
      email        — prospect email (required)
      cadence_name — name of the cadence to start (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    email = merged.get("email") or ""
    cadence_name = merged.get("cadence_name") or ""

    if not email:
        raise ValueError("email is required for klenty.start_cadence")
    if not cadence_name:
        raise ValueError("cadence_name is required for klenty.start_cadence")

    headers = {"x-API-Key": api_key}
    url = f"{KLENTY_BASE}/prospect/start-cadence"
    payload = {"email": email, "cadenceName": cadence_name}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("klenty.start_cadence", email=email, cadence_name=cadence_name)
    return {"result": data}
