"""
LoneScale sales intelligence integration.

Provides contact enrichment and company search via the LoneScale API v1.

Credential fields:
  - api_key : LoneScale API key (Bearer auth)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.lonescale.com/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("LoneScale credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"LoneScale API error {r.status_code}: {detail}")


@register_node("lonescale.enrich_contact")
async def lonescale_enrich_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Enrich a contact with LoneScale sales intelligence data."""
    email = config.get("email") or input_data.get("email")
    linkedin_url = config.get("linkedin_url") or input_data.get("linkedin_url")

    if not email and not linkedin_url:
        raise ValueError("lonescale.enrich_contact requires 'email' or 'linkedin_url'")

    payload: dict = {}
    if email:
        payload["email"] = email
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url

    log.info("lonescale.enrich_contact", email=email)
    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts/enrich", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"contact": data}


@register_node("lonescale.search_companies")
async def lonescale_search_companies(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search for companies using LoneScale."""
    query = config.get("query") or input_data.get("query")
    domain = config.get("domain") or input_data.get("domain")
    industry = config.get("industry") or input_data.get("industry")
    limit = min(int(config.get("limit") or input_data.get("limit", 10)), 100)

    payload: dict = {"limit": limit}
    if query:
        payload["query"] = query
    if domain:
        payload["domain"] = domain
    if industry:
        payload["industry"] = industry

    log.info("lonescale.search_companies", query=query, domain=domain, limit=limit)
    async with await _client(credential_id, db) as client:
        r = await client.post("/companies/search", json=payload)
        _raise_for_status(r)
        data = r.json()

    companies = data.get("companies", data) if isinstance(data, dict) else data
    return {"companies": companies, "count": len(companies) if isinstance(companies, list) else 0}


@register_node("lonescale.get_company")
async def lonescale_get_company(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get detailed information about a company from LoneScale."""
    company_id = config.get("company_id") or input_data.get("company_id")
    domain = config.get("domain") or input_data.get("domain")

    if not company_id and not domain:
        raise ValueError("lonescale.get_company requires 'company_id' or 'domain'")

    log.info("lonescale.get_company", company_id=company_id, domain=domain)
    async with await _client(credential_id, db) as client:
        if company_id:
            r = await client.get(f"/companies/{company_id}")
        else:
            r = await client.get("/companies/lookup", params={"domain": domain})
        _raise_for_status(r)
        data = r.json()

    return {"company": data}
