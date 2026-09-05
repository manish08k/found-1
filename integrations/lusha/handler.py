"""Lusha B2B data enrichment integration — person and company enrichment."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

LUSHA_BASE = "https://api.lusha.com/v1"


@register_node("lusha.enrich_person")
async def lusha_enrich_person(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enrich a person's contact data using Lusha.

    config/input_data:
      api_key    — Lusha API key (required)
      first_name — first name (required)
      last_name  — last name (required)
      company    — company name (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    company = merged.get("company") or ""

    if not fn or not ln:
        raise ValueError("first_name and last_name are required for lusha.enrich_person")
    if not company:
        raise ValueError("company is required for lusha.enrich_person")

    headers = {"api_key": api_key}
    url = f"{LUSHA_BASE}/person"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            url,
            headers=headers,
            params={"firstName": fn, "lastName": ln, "company": company},
        )
        r.raise_for_status()
        data = r.json()

    log.info("lusha.enrich_person", first_name=fn, last_name=ln, company=company)
    return {"person": data}


@register_node("lusha.enrich_company")
async def lusha_enrich_company(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enrich company data using Lusha.

    config/input_data:
      api_key — Lusha API key (required)
      domain  — company domain, e.g. 'acme.com' (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    domain = merged.get("domain") or ""

    if not domain:
        raise ValueError("domain is required for lusha.enrich_company")

    headers = {"api_key": api_key}
    url = f"{LUSHA_BASE}/company"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"domain": domain})
        r.raise_for_status()
        data = r.json()

    log.info("lusha.enrich_company", domain=domain)
    return {"company": data}
