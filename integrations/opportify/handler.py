"""Opportify company intelligence and enrichment integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERVICE_BASE = "https://api.opportify.ai/insights/v1"


@register_node("opportify.search_companies")
async def opportify_search_companies(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search companies using Opportify."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for opportify.search_companies")
    query = merged.get("query", "")
    params = {"query": query}
    if merged.get("limit"):
        params["limit"] = merged["limit"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get("/companies/search", headers={"api-key": api_key}, params=params)
        r.raise_for_status()
        data = r.json()
    companies = data if isinstance(data, list) else data.get("companies", data.get("results", []))
    log.info("opportify.search_companies", count=len(companies))
    return {"companies": companies, "raw": data}


@register_node("opportify.get_company")
async def opportify_get_company(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a company by domain or ID from Opportify."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for opportify.get_company")
    company_id = merged.get("company_id", merged.get("domain", ""))
    if not company_id:
        raise ValueError("company_id or domain is required for opportify.get_company")
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get(f"/companies/{company_id}", headers={"api-key": api_key})
        r.raise_for_status()
        data = r.json()
    log.info("opportify.get_company", company_id=company_id)
    return {"company": data}


@register_node("opportify.enrich_company")
async def opportify_enrich_company(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enrich company data using Opportify."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for opportify.enrich_company")
    domain = merged.get("domain", "")
    if not domain:
        raise ValueError("domain is required for opportify.enrich_company")
    payload = {"domain": domain}
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.post("/companies/enrich", headers={"api-key": api_key}, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("opportify.enrich_company", domain=domain)
    return {"enriched": data}
