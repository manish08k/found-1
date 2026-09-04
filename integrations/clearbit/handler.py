"""
Clearbit data enrichment integration.

Credential fields:
  - api_key: Clearbit API key

Auth: Authorization: Bearer {api_key}
Base URLs:
  - Person API: https://person.clearbit.com
  - Company API: https://company.clearbit.com
  - Prospector API: https://prospector.clearbit.com
  - Risk API: https://risk.clearbit.com
  - Reveal API: https://reveal.clearbit.com
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

PERSON_URL = "https://person.clearbit.com"
COMPANY_URL = "https://company.clearbit.com"
PROSPECTOR_URL = "https://prospector.clearbit.com"
REVEAL_URL = "https://reveal.clearbit.com"
ENRICHMENT_URL = "https://person.clearbit.com"


async def _get_api_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Clearbit credential is missing 'api_key'")
    return api_key


def _make_client(base_url: str, api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Clearbit API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Person enrichment
# ---------------------------------------------------------------------------

@register_node("clearbit.enrich_person")
async def clearbit_enrich_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/people/find — enrich a person by email."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("clearbit.enrich_person requires 'email'")
    api_key = await _get_api_key(credential_id, db)
    params: dict = {"email": email}
    given_name = config.get("given_name") or input_data.get("given_name")
    if given_name:
        params["given_name"] = given_name
    family_name = config.get("family_name") or input_data.get("family_name")
    if family_name:
        params["family_name"] = family_name
    async with _make_client(PERSON_URL, api_key) as client:
        r = await client.get("/v2/people/find", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Company enrichment
# ---------------------------------------------------------------------------

@register_node("clearbit.enrich_company")
async def clearbit_enrich_company(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/companies/find — enrich a company by domain."""
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("clearbit.enrich_company requires 'domain'")
    api_key = await _get_api_key(credential_id, db)
    async with _make_client(COMPANY_URL, api_key) as client:
        r = await client.get("/v2/companies/find", params={"domain": domain})
    return _check(r)


# ---------------------------------------------------------------------------
# Email finder
# ---------------------------------------------------------------------------

@register_node("clearbit.find_email")
async def clearbit_find_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v1/email-addresses/find — find a person's email by name and domain."""
    domain = config.get("domain") or input_data.get("domain")
    name = config.get("name") or input_data.get("name")
    if not domain:
        raise ValueError("clearbit.find_email requires 'domain'")
    if not name:
        raise ValueError("clearbit.find_email requires 'name'")
    api_key = await _get_api_key(credential_id, db)
    params: dict = {"domain": domain, "name": name}
    async with _make_client(PERSON_URL, api_key) as client:
        r = await client.get("/v1/email-addresses/find", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Prospector search
# ---------------------------------------------------------------------------

@register_node("clearbit.prospect_search")
async def clearbit_prospect_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v2/people/search — search for prospects (Prospector API)."""
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("clearbit.prospect_search requires 'domain'")
    api_key = await _get_api_key(credential_id, db)
    params: dict = {"domain": domain}
    for field in ("role", "seniority", "title", "city", "state", "country",
                  "name", "page", "page_size"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            params[field] = v
    async with _make_client(PROSPECTOR_URL, api_key) as client:
        r = await client.get("/v2/people/search", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# IP Reveal
# ---------------------------------------------------------------------------

@register_node("clearbit.reveal_ip")
async def clearbit_reveal_ip(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /v1/companies/find — reveal the company behind an IP address."""
    ip = config.get("ip") or input_data.get("ip")
    if not ip:
        raise ValueError("clearbit.reveal_ip requires 'ip'")
    api_key = await _get_api_key(credential_id, db)
    async with _make_client(REVEAL_URL, api_key) as client:
        r = await client.get("/v1/companies/find", params={"ip": ip})
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Clearbit connection by making a minimal company lookup."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with _make_client(COMPANY_URL, api_key) as client:
        r = await client.get("/v2/companies/find", params={"domain": "clearbit.com"})
    # 200 or 202 (pending) are both valid
    if r.status_code not in (200, 202, 404):
        raise ValueError(f"Clearbit connection failed: {r.status_code} {r.text}")
    return {"ok": True, "status_code": r.status_code}
