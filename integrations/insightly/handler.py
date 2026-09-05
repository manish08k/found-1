"""Insightly CRM integration — contacts and opportunities."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

INSIGHTLY_BASE = "https://api.insightly.com/v3.1"


@register_node("insightly.list_contacts")
async def insightly_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts from Insightly CRM.

    config/input_data:
      api_key — Insightly API key (required, used as HTTP Basic username)
      top     — number of records to return (default 50)
      skip    — records to skip for pagination (default 0)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    top = int(merged.get("top", 50))
    skip = int(merged.get("skip", 0))

    url = f"{INSIGHTLY_BASE}/Contacts"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""), params={"top": top, "skip": skip})
        r.raise_for_status()
        data = r.json()

    log.info("insightly.list_contacts", count=len(data) if isinstance(data, list) else None)
    return {"contacts": data}


@register_node("insightly.create_contact")
async def insightly_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact in Insightly CRM.

    config/input_data:
      api_key    — Insightly API key (required)
      first_name — first name (required)
      last_name  — last name
      email      — email address
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""

    if not fn:
        raise ValueError("first_name is required for insightly.create_contact")

    url = f"{INSIGHTLY_BASE}/Contacts"
    payload: dict = {"FIRST_NAME": fn, "LAST_NAME": ln}
    if email:
        payload["EMAIL_ADDRESS"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, auth=(api_key, ""), json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("insightly.create_contact", first_name=fn, last_name=ln, id=data.get("CONTACT_ID"))
    return {"contact": data, "id": data.get("CONTACT_ID")}


@register_node("insightly.list_opportunities")
async def insightly_list_opportunities(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List opportunities from Insightly CRM.

    config/input_data:
      api_key — Insightly API key (required)
      top     — number of records to return (default 50)
      skip    — records to skip for pagination (default 0)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    top = int(merged.get("top", 50))
    skip = int(merged.get("skip", 0))

    url = f"{INSIGHTLY_BASE}/Opportunities"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""), params={"top": top, "skip": skip})
        r.raise_for_status()
        data = r.json()

    log.info("insightly.list_opportunities", count=len(data) if isinstance(data, list) else None)
    return {"opportunities": data}


@register_node("insightly.create_opportunity")
async def insightly_create_opportunity(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new opportunity in Insightly CRM.

    config/input_data:
      api_key             — Insightly API key (required)
      name                — opportunity name (required)
      responsible_user_id — user ID to assign to (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    name = merged.get("name") or ""
    user_id = merged.get("responsible_user_id") or merged.get("user_id")

    if not name:
        raise ValueError("name is required for insightly.create_opportunity")

    url = f"{INSIGHTLY_BASE}/Opportunities"
    payload: dict = {"OPPORTUNITY_NAME": name}
    if user_id:
        payload["RESPONSIBLE_USER_ID"] = user_id

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, auth=(api_key, ""), json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("insightly.create_opportunity", name=name, id=data.get("OPPORTUNITY_ID"))
    return {"opportunity": data, "id": data.get("OPPORTUNITY_ID")}
