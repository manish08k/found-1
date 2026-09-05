"""Capsule CRM integration — contacts and opportunities."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CAPSULE_BASE = "https://api.capsulecrm.com/api/v2"


@register_node("capsule_crm.list_contacts")
async def capsule_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts (parties) from Capsule CRM.

    config/input_data:
      api_key  — Capsule API key (required)
      per_page — results per page (default 50)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    per_page = int(merged.get("per_page", 50))

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{CAPSULE_BASE}/parties"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"perPage": per_page})
        r.raise_for_status()
        data = r.json()

    parties = data.get("parties", data)
    log.info("capsule_crm.list_contacts", count=len(parties) if isinstance(parties, list) else None)
    return {"contacts": parties}


@register_node("capsule_crm.get_contact")
async def capsule_get_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Capsule CRM contact by ID.

    config/input_data:
      api_key — Capsule API key (required)
      id      — party ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    contact_id = merged.get("id") or ""

    if not contact_id:
        raise ValueError("id is required for capsule_crm.get_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{CAPSULE_BASE}/parties/{contact_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    party = data.get("party", data)
    log.info("capsule_crm.get_contact", id=contact_id)
    return {"contact": party}


@register_node("capsule_crm.create_contact")
async def capsule_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new person contact in Capsule CRM.

    config/input_data:
      api_key    — Capsule API key (required)
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
        raise ValueError("first_name is required for capsule_crm.create_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{CAPSULE_BASE}/parties"
    payload = {
        "party": {
            "type": "person",
            "firstName": fn,
            "lastName": ln,
            "emailAddresses": [{"address": email}] if email else [],
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    party = data.get("party", data)
    log.info("capsule_crm.create_contact", first_name=fn, last_name=ln)
    return {"contact": party}


@register_node("capsule_crm.list_opportunities")
async def capsule_list_opportunities(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List opportunities from Capsule CRM.

    config/input_data:
      api_key  — Capsule API key (required)
      per_page — results per page (default 50)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    per_page = int(merged.get("per_page", 50))

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{CAPSULE_BASE}/opportunities"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"perPage": per_page})
        r.raise_for_status()
        data = r.json()

    opportunities = data.get("opportunities", data)
    log.info("capsule_crm.list_opportunities", count=len(opportunities) if isinstance(opportunities, list) else None)
    return {"opportunities": opportunities}
