"""Teamleader Focus CRM/PM integration — companies, contacts, and deals."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TEAMLEADER_BASE = "https://api.focus.teamleader.eu"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("teamleader.list_companies")
async def teamleader_list_companies(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List companies in Teamleader Focus.

    config:
      access_token — OAuth2 access token (required)
      page_size    — number of results per page (default 20)
      page_number  — page number (default 1)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for teamleader.list_companies")

    page_size = int(config.get("page_size", 20))
    page_number = int(config.get("page_number", 1))
    payload = {"page": {"size": page_size, "number": page_number}}

    async with httpx.AsyncClient(base_url=TEAMLEADER_BASE, timeout=30) as client:
        r = await client.post("/companies.list", json=payload, headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    companies = data.get("data", [])
    log.info("teamleader.list_companies", count=len(companies))
    return {"companies": companies, "count": len(companies)}


@register_node("teamleader.list_contacts")
async def teamleader_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts in Teamleader Focus.

    config:
      access_token — OAuth2 access token (required)
      page_size    — number of results per page (default 20)
      page_number  — page number (default 1)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for teamleader.list_contacts")

    page_size = int(config.get("page_size", 20))
    page_number = int(config.get("page_number", 1))
    payload = {"page": {"size": page_size, "number": page_number}}

    async with httpx.AsyncClient(base_url=TEAMLEADER_BASE, timeout=30) as client:
        r = await client.post("/contacts.list", json=payload, headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    contacts = data.get("data", [])
    log.info("teamleader.list_contacts", count=len(contacts))
    return {"contacts": contacts, "count": len(contacts)}


@register_node("teamleader.create_company")
async def teamleader_create_company(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a company in Teamleader Focus.

    config/input_data:
      access_token — OAuth2 access token (required)
      name         — company name (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for teamleader.create_company")

    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("name is required for teamleader.create_company")

    payload = {"name": name}

    async with httpx.AsyncClient(base_url=TEAMLEADER_BASE, timeout=30) as client:
        r = await client.post("/companies.create", json=payload, headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    company_id = data.get("data", {}).get("id")
    log.info("teamleader.create_company", company_id=company_id, name=name)
    return {"result": data, "company_id": company_id}


@register_node("teamleader.list_deals")
async def teamleader_list_deals(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List deals in Teamleader Focus.

    config:
      access_token — OAuth2 access token (required)
      page_size    — number of results per page (default 20)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for teamleader.list_deals")

    page_size = int(config.get("page_size", 20))
    payload = {"page": {"size": page_size}}

    async with httpx.AsyncClient(base_url=TEAMLEADER_BASE, timeout=30) as client:
        r = await client.post("/deals.list", json=payload, headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    deals = data.get("data", [])
    log.info("teamleader.list_deals", count=len(deals))
    return {"deals": deals, "count": len(deals)}
