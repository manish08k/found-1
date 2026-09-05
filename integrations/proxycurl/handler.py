"""ProxyCurl LinkedIn data integration — person, company, and search."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PROXYCURL_BASE = "https://nubela.co/proxycurl/api/v2"


@register_node("proxycurl.get_person")
async def proxycurl_get_person(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch a LinkedIn person profile via ProxyCurl.

    config/input_data:
      api_key       — ProxyCurl API key (required)
      linkedin_url  — LinkedIn profile URL (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    linkedin_url = merged.get("linkedin_url") or merged.get("url") or ""

    if not linkedin_url:
        raise ValueError("linkedin_url is required for proxycurl.get_person")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{PROXYCURL_BASE}/linkedin"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"url": linkedin_url})
        r.raise_for_status()
        data = r.json()

    log.info("proxycurl.get_person", linkedin_url=linkedin_url)
    return {"person": data}


@register_node("proxycurl.get_company")
async def proxycurl_get_company(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch a LinkedIn company profile via ProxyCurl.

    config/input_data:
      api_key      — ProxyCurl API key (required)
      linkedin_url — LinkedIn company page URL (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    linkedin_url = merged.get("linkedin_url") or merged.get("url") or ""

    if not linkedin_url:
        raise ValueError("linkedin_url is required for proxycurl.get_company")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{PROXYCURL_BASE}/linkedin/company"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"url": linkedin_url})
        r.raise_for_status()
        data = r.json()

    log.info("proxycurl.get_company", linkedin_url=linkedin_url)
    return {"company": data}


@register_node("proxycurl.search_person")
async def proxycurl_search_person(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search for a LinkedIn person by name and company domain via ProxyCurl.

    config/input_data:
      api_key        — ProxyCurl API key (required)
      first_name     — first name (required)
      last_name      — last name
      company_domain — company domain, e.g. 'acme.com'
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    domain = merged.get("company_domain") or ""

    if not fn:
        raise ValueError("first_name is required for proxycurl.search_person")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{PROXYCURL_BASE}/search/person"
    params: dict = {"first_name": fn}
    if ln:
        params["last_name"] = ln
    if domain:
        params["company_domain"] = domain

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

    results = data.get("results", data)
    log.info("proxycurl.search_person", first_name=fn, last_name=ln, count=len(results) if isinstance(results, list) else None)
    return {"results": results, "total_result_count": data.get("total_result_count")}
