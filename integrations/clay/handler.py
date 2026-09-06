"""Clay integration for people and company enrichment and search."""
import httpx
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.clay.com/v1"


def _get_headers(api_key: str) -> dict:
    return {
        "x-clay-api-key": api_key,
        "Content-Type": "application/json",
    }


@register_node("clay.search_people")
async def clay_search_people(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search for people using Clay's people search."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("clay requires 'api_key'")

    payload = {}
    for field in ["name", "email", "linkedin_url", "company", "title", "location"]:
        if merged.get(field):
            payload[field] = merged[field]
    if not payload:
        raise ValueError("search_people requires at least one search field")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/sources/people-search", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        return r.json()


@register_node("clay.enrich_person")
async def clay_enrich_person(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enrich a person's profile with additional data."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    email = merged.get("email")
    linkedin_url = merged.get("linkedin_url")
    if not email and not linkedin_url:
        raise ValueError("enrich_person requires 'email' or 'linkedin_url'")

    payload = {}
    if email:
        payload["email"] = email
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    for field in ["name", "company", "title"]:
        if merged.get(field):
            payload[field] = merged[field]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/sources/person-enrichment", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        return r.json()


@register_node("clay.search_companies")
async def clay_search_companies(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search for companies using Clay's company search."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")

    payload = {}
    for field in ["name", "domain", "industry", "location", "employee_count_min", "employee_count_max"]:
        if merged.get(field) is not None:
            payload[field] = merged[field]
    if not payload:
        raise ValueError("search_companies requires at least one search field")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/sources/company-search", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        return r.json()


@register_node("clay.enrich_company")
async def clay_enrich_company(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enrich a company's profile with additional data."""
    merged = {**config, **input_data}
    if credential_id:
        creds = await get_credential_data(credential_id, db)
    else:
        creds = merged
    api_key = creds.get("api_key")
    domain = merged.get("domain")
    name = merged.get("name")
    if not domain and not name:
        raise ValueError("enrich_company requires 'domain' or 'name'")

    payload = {}
    if domain:
        payload["domain"] = domain
    if name:
        payload["name"] = name

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/sources/company-enrichment", headers=_get_headers(api_key), json=payload)
        r.raise_for_status()
        return r.json()
