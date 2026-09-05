"""Salesmate CRM integration — contacts and deals management.

Credential fields:
  - url           : Salesmate instance URL (e.g. https://yourcompany.salesmate.io)
  - api_key       : Salesmate API key
  - session_token : Salesmate session token

Auth: api_key + session_token headers
Base URL: {url}/apis/

Nodes:
  - salesmate.list_contacts  : list/search contacts
  - salesmate.create_contact : create a new contact
  - salesmate.list_deals     : list/search deals (companies)
  - salesmate.create_deal    : create a new deal
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------

async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    url = creds.get("url", "").rstrip("/")
    api_key = creds.get("api_key")
    session_token = creds.get("session_token")

    if not url:
        raise ValueError("Salesmate credential is missing 'url'")
    if not api_key:
        raise ValueError("Salesmate credential is missing 'api_key'")
    if not session_token:
        raise ValueError("Salesmate credential is missing 'session_token'")

    base_url = f"{url}/apis/"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "accesskey": api_key,
            "x-linkname": session_token,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("salesmate.list_contacts")
async def list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List or search Salesmate contacts."""
    page = int(config.get("page", input_data.get("page", 1)))
    per_page = int(config.get("per_page", input_data.get("per_page", 20)))
    query = config.get("query") or input_data.get("query")

    params: dict = {"page": page, "perPage": per_page}
    if query:
        params["query"] = query

    log.info("salesmate.list_contacts", page=page, per_page=per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get("contacts", params=params)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("data", {}).get("data", data.get("data", []))
    total = data.get("data", {}).get("total", len(contacts) if isinstance(contacts, list) else 0)
    log.info("salesmate.list_contacts.done", count=len(contacts) if isinstance(contacts, list) else 0)
    return {"contacts": contacts, "total": total, "page": page, "per_page": per_page}


@register_node("salesmate.create_contact")
async def create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact in Salesmate."""
    first_name = config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    email = config.get("email") or input_data.get("email", "")
    phone = config.get("phone") or input_data.get("phone", "")
    company = config.get("company") or input_data.get("company", "")

    if not (first_name or last_name):
        raise ValueError("At least 'first_name' or 'last_name' is required")

    payload: dict = {
        "firstName": first_name,
        "lastName": last_name,
    }
    if email:
        payload["email"] = email
    if phone:
        payload["phone"] = phone
    if company:
        payload["company"] = company

    # Merge any extra fields from config
    extra = config.get("fields") or input_data.get("fields", {})
    if isinstance(extra, dict):
        payload.update(extra)

    log.info("salesmate.create_contact", email=email)
    async with await _client(credential_id, db) as client:
        r = await client.post("contacts", json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("data", data)
    log.info("salesmate.create_contact.done", contact_id=contact.get("id"))
    return {"contact": contact, "contact_id": contact.get("id")}


@register_node("salesmate.list_deals")
async def list_deals(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List or search Salesmate deals."""
    page = int(config.get("page", input_data.get("page", 1)))
    per_page = int(config.get("per_page", input_data.get("per_page", 20)))
    query = config.get("query") or input_data.get("query")

    params: dict = {"page": page, "perPage": per_page}
    if query:
        params["query"] = query

    log.info("salesmate.list_deals", page=page, per_page=per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get("deals", params=params)
        r.raise_for_status()
        data = r.json()

    deals = data.get("data", {}).get("data", data.get("data", []))
    total = data.get("data", {}).get("total", len(deals) if isinstance(deals, list) else 0)
    log.info("salesmate.list_deals.done", count=len(deals) if isinstance(deals, list) else 0)
    return {"deals": deals, "total": total, "page": page, "per_page": per_page}


@register_node("salesmate.create_deal")
async def create_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new deal in Salesmate."""
    title = config.get("title") or input_data.get("title")
    if not title:
        raise ValueError("'title' is required for creating a deal")

    owner_id = config.get("owner_id") or input_data.get("owner_id")
    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")
    stage_id = config.get("stage_id") or input_data.get("stage_id")
    deal_value = config.get("deal_value") or input_data.get("deal_value")
    currency = config.get("currency") or input_data.get("currency", "USD")
    contact_ids = config.get("contact_ids") or input_data.get("contact_ids", [])

    payload: dict = {"title": title, "currency": currency}
    if owner_id:
        payload["ownerId"] = owner_id
    if pipeline_id:
        payload["pipelineId"] = pipeline_id
    if stage_id:
        payload["stageId"] = stage_id
    if deal_value is not None:
        payload["dealValue"] = deal_value
    if contact_ids:
        payload["contactIds"] = contact_ids

    extra = config.get("fields") or input_data.get("fields", {})
    if isinstance(extra, dict):
        payload.update(extra)

    log.info("salesmate.create_deal", title=title)
    async with await _client(credential_id, db) as client:
        r = await client.post("deals", json=payload)
        r.raise_for_status()
        data = r.json()

    deal = data.get("data", data)
    log.info("salesmate.create_deal.done", deal_id=deal.get("id"))
    return {"deal": deal, "deal_id": deal.get("id")}
