"""UpLead B2B lead enrichment integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

UPLEAD_BASE = "https://api.uplead.com/v2"


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


@register_node("uplead.enrich_person")
async def enrich_person(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enrich a person record by email address.

    config/input_data:
      api_key — UpLead API key (required)
      email   — email address to enrich (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    email = merged.get("email") or ""

    if not api_key:
        raise ValueError("api_key is required for uplead.enrich_person")
    if not email:
        raise ValueError("email is required for uplead.enrich_person")

    payload = {"email": email}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{UPLEAD_BASE}/person-search", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    log.info("uplead.enrich_person", email=email)
    return {"person": data.get("data", data), "credits_used": data.get("meta", {}).get("credits_used")}


@register_node("uplead.search_companies")
async def search_companies(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search for companies by domain or name.

    config/input_data:
      api_key      — UpLead API key (required)
      domain       — company domain (optional if company_name provided)
      company_name — company name (optional if domain provided)
      location     — location filter (optional)
      industry     — industry filter (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    domain = merged.get("domain") or ""
    company_name = merged.get("company_name") or ""
    location = merged.get("location") or ""
    industry = merged.get("industry") or ""

    if not api_key:
        raise ValueError("api_key is required for uplead.search_companies")
    if not domain and not company_name:
        raise ValueError("Either domain or company_name is required for uplead.search_companies")

    payload: dict = {}
    if domain:
        payload["domain"] = domain
    if company_name:
        payload["company_name"] = company_name
    if location:
        payload["location"] = location
    if industry:
        payload["industry"] = industry

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{UPLEAD_BASE}/company-search", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    companies = data.get("data", data)
    log.info("uplead.search_companies", domain=domain, company_name=company_name)
    return {"companies": companies, "meta": data.get("meta", {})}


@register_node("uplead.get_credits")
async def get_credits(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get remaining UpLead API credits for the account.

    config/input_data:
      api_key — UpLead API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    if not api_key:
        raise ValueError("api_key is required for uplead.get_credits")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{UPLEAD_BASE}/user/credits", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    credits = data.get("data", data)
    log.info("uplead.get_credits", credits=credits)
    return {"credits": credits}
