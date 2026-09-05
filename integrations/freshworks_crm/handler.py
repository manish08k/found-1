"""
Freshworks CRM (Freshsales) integration.

Provides contact and deal management via the Freshworks CRM Sales API.

Credential fields:
  - api_key : Freshworks CRM API key
  - domain  : Your Freshworks subdomain, e.g. "yourcompany"
              (will be used in https://{domain}.myfreshworks.com)

Auth: Authorization: Token token={api_key}
Base URL: https://{domain}.myfreshworks.com/crm/sales/api/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    domain = creds.get("domain", "").strip().rstrip("/")
    if not api_key:
        raise ValueError("Freshworks CRM credential missing 'api_key'")
    if not domain:
        raise ValueError("Freshworks CRM credential missing 'domain'")
    base_url = f"https://{domain}.myfreshworks.com/crm/sales/api"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Token token={api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"Freshworks CRM API error {r.status_code}: {detail}")


@register_node("freshworks_crm.list_contacts")
async def list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List contacts from Freshworks CRM with optional filtering."""
    page = int(config.get("page", 1))
    per_page = int(config.get("per_page", 25))
    sort = config.get("sort", "created_at")
    sort_type = config.get("sort_type", "desc")  # asc or desc
    view_id = config.get("view_id") or input_data.get("view_id")
    search = config.get("search") or input_data.get("search")

    params: dict = {
        "page": page,
        "per_page": per_page,
        "sort": sort,
        "sort_type": sort_type,
        "include": "owner,creater,updater,source,contact_status",
    }
    if view_id:
        params["view_id"] = view_id

    log.info("freshworks_crm.list_contacts", page=page, per_page=per_page)

    async with await _client(credential_id, db) as client:
        if search:
            # Use the search endpoint for keyword queries
            r = await client.get(
                "/contacts/search",
                params={**params, "q": search, "include": "contact_status,owner"},
            )
        else:
            r = await client.get("/contacts/view/filters/all/contacts", params=params)
        _raise_for_status(r)
        data = r.json()

    contacts = data.get("contacts", data.get("results", []))
    meta = data.get("meta", {})
    log.info("freshworks_crm.list_contacts.done", count=len(contacts))
    return {
        "contacts": contacts,
        "count": len(contacts),
        "meta": meta,
        "page": page,
    }


@register_node("freshworks_crm.create_contact")
async def create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact in Freshworks CRM."""
    # Required fields
    first_name = config.get("first_name") or input_data.get("first_name")
    last_name = config.get("last_name") or input_data.get("last_name")
    email = config.get("email") or input_data.get("email")

    if not email and not (first_name or last_name):
        raise ValueError("At least 'email' or a name ('first_name'/'last_name') is required")

    contact: dict = {}
    if first_name:
        contact["first_name"] = first_name
    if last_name:
        contact["last_name"] = last_name
    if email:
        contact["email"] = email

    # Optional standard fields
    optional_fields = [
        "mobile_number", "work_number", "address", "city", "state",
        "zipcode", "country", "job_title", "department", "linkedin",
        "twitter", "facebook", "owner_id", "contact_status_id",
        "lead_source_id", "lifecycle_stage_id",
    ]
    for f in optional_fields:
        val = config.get(f) or input_data.get(f)
        if val is not None:
            contact[f] = val

    # Custom fields
    custom_fields = config.get("custom_field") or input_data.get("custom_field") or {}
    if custom_fields:
        contact["custom_field"] = custom_fields

    log.info("freshworks_crm.create_contact", email=email)

    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts", json={"contact": contact})
        _raise_for_status(r)
        data = r.json()

    result = data.get("contact", data)
    log.info("freshworks_crm.create_contact.done", contact_id=result.get("id"))
    return {"contact": result, "contact_id": result.get("id")}


@register_node("freshworks_crm.create_deal")
async def create_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new deal (opportunity) in Freshworks CRM."""
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("'name' is required for a deal")

    deal: dict = {"name": name}

    optional_fields = [
        "amount", "base_currency_amount", "expected_close",
        "owner_id", "pipeline_id", "deal_stage_id", "deal_type_id",
        "deal_reason_id", "deal_source_id", "currency_id",
        "probability", "contacts", "account_id",
    ]
    for f in optional_fields:
        val = config.get(f) or input_data.get(f)
        if val is not None:
            deal[f] = val

    # Link to contacts
    contact_ids = config.get("contact_ids") or input_data.get("contact_ids")
    if contact_ids:
        if isinstance(contact_ids, list):
            deal["contacts"] = [{"id": cid} for cid in contact_ids]
        else:
            deal["contacts"] = [{"id": contact_ids}]

    custom_fields = config.get("custom_field") or input_data.get("custom_field") or {}
    if custom_fields:
        deal["custom_field"] = custom_fields

    log.info("freshworks_crm.create_deal", name=name)

    async with await _client(credential_id, db) as client:
        r = await client.post("/deals", json={"deal": deal})
        _raise_for_status(r)
        data = r.json()

    result = data.get("deal", data)
    log.info("freshworks_crm.create_deal.done", deal_id=result.get("id"))
    return {"deal": result, "deal_id": result.get("id")}


@register_node("freshworks_crm.list_deals")
async def list_deals(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List deals from Freshworks CRM with optional filtering."""
    page = int(config.get("page", 1))
    per_page = int(config.get("per_page", 25))
    sort = config.get("sort", "created_at")
    sort_type = config.get("sort_type", "desc")
    view_id = config.get("view_id") or input_data.get("view_id")
    search = config.get("search") or input_data.get("search")

    params: dict = {
        "page": page,
        "per_page": per_page,
        "sort": sort,
        "sort_type": sort_type,
        "include": "owner,creater,updater,source,deal_stage,pipeline,currency",
    }
    if view_id:
        params["view_id"] = view_id

    log.info("freshworks_crm.list_deals", page=page, per_page=per_page)

    async with await _client(credential_id, db) as client:
        if search:
            r = await client.get(
                "/deals/search",
                params={**params, "q": search},
            )
        else:
            r = await client.get("/deals/view/filters/all/deals", params=params)
        _raise_for_status(r)
        data = r.json()

    deals = data.get("deals", data.get("results", []))
    meta = data.get("meta", {})
    log.info("freshworks_crm.list_deals.done", count=len(deals))
    return {
        "deals": deals,
        "count": len(deals),
        "meta": meta,
        "page": page,
    }
