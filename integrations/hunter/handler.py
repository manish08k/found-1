"""
Hunter.io email finding and verification integration.

Credential fields:
  - api_key: Hunter.io API key (passed as query param)

Auth: api_key query parameter
Base URL: https://api.hunter.io/v2
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.hunter.io/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Hunter credential is missing 'api_key'")
    # Store api_key on the client for use in params
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=30.0,
    )
    client._hunter_api_key = api_key  # type: ignore[attr-defined]
    return client


def _params(client: httpx.AsyncClient, extra: dict | None = None) -> dict:
    """Build params dict that always includes api_key."""
    p: dict = {"api_key": client._hunter_api_key}  # type: ignore[attr-defined]
    if extra:
        p.update({k: v for k, v in extra.items() if v is not None})
    return p


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Hunter API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


# ---------------------------------------------------------------------------
# Domain Search & Email Finder
# ---------------------------------------------------------------------------

@register_node("hunter.domain_search")
async def hunter_domain_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /domain-search — search all email addresses for a domain."""
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("hunter.domain_search requires 'domain'")
    extra: dict = {"domain": domain}
    for field in ("limit", "offset", "type", "seniority", "department"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            extra[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/domain-search", params=_params(client, extra))
    return _check(r)


@register_node("hunter.email_finder")
async def hunter_email_finder(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /email-finder — find the most likely email for a person at a domain."""
    domain = config.get("domain") or input_data.get("domain")
    first_name = config.get("first_name") or input_data.get("first_name")
    last_name = config.get("last_name") or input_data.get("last_name")
    company = config.get("company") or input_data.get("company")
    if not (domain or company):
        raise ValueError("hunter.email_finder requires 'domain' or 'company'")
    if not first_name or not last_name:
        raise ValueError("hunter.email_finder requires 'first_name' and 'last_name'")
    extra: dict = {"first_name": first_name, "last_name": last_name}
    if domain:
        extra["domain"] = domain
    if company:
        extra["company"] = company
    async with await _client(credential_id, db) as client:
        r = await client.get("/email-finder", params=_params(client, extra))
    return _check(r)


@register_node("hunter.email_verifier")
async def hunter_email_verifier(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /email-verifier — verify an email address."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("hunter.email_verifier requires 'email'")
    async with await _client(credential_id, db) as client:
        r = await client.get("/email-verifier", params=_params(client, {"email": email}))
    return _check(r)


@register_node("hunter.email_count")
async def hunter_email_count(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /email-count — count email addresses for a domain."""
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("hunter.email_count requires 'domain'")
    extra: dict = {"domain": domain}
    email_type = config.get("type") or input_data.get("type")
    if email_type:
        extra["type"] = email_type
    async with await _client(credential_id, db) as client:
        r = await client.get("/email-count", params=_params(client, extra))
    return _check(r)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@register_node("hunter.create_lead")
async def hunter_create_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /leads — create a new lead."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("hunter.create_lead requires 'email'")
    body: dict = {"email": email}
    for field in ("first_name", "last_name", "position", "company", "company_industry",
                  "company_size", "confidence_score", "website", "country_code",
                  "phone_number", "twitter", "linkedin_url", "notes", "source"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            body[field] = v
    leads_list_id = config.get("leads_list_id") or input_data.get("leads_list_id")
    if leads_list_id:
        body["leads_list_id"] = leads_list_id
    async with await _client(credential_id, db) as client:
        r = await client.post("/leads", params=_params(client), json=body)
    return _check(r)


@register_node("hunter.list_leads")
async def hunter_list_leads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /leads — list all leads."""
    extra: dict = {}
    for field in ("offset", "limit", "leads_list_id"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            extra[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/leads", params=_params(client, extra))
    return _check(r)


@register_node("hunter.get_lead")
async def hunter_get_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /leads/{lead_id} — get a lead by ID."""
    lead_id = config.get("lead_id") or input_data.get("lead_id")
    if not lead_id:
        raise ValueError("hunter.get_lead requires 'lead_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/leads/{lead_id}", params=_params(client))
    return _check(r)


@register_node("hunter.delete_lead")
async def hunter_delete_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /leads/{lead_id} — delete a lead."""
    lead_id = config.get("lead_id") or input_data.get("lead_id")
    if not lead_id:
        raise ValueError("hunter.delete_lead requires 'lead_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/leads/{lead_id}", params=_params(client))
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Hunter API error {r.status_code}: {detail}")
    return {"ok": True, "lead_id": lead_id}


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@register_node("hunter.list_campaigns")
async def hunter_list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /campaigns — list email campaigns."""
    extra: dict = {}
    for field in ("offset", "limit"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            extra[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.get("/campaigns", params=_params(client, extra))
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(creds: dict) -> dict:
    """Test Hunter connection by fetching account info."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Missing 'api_key'")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get("/account", params={"api_key": api_key})
    if not r.is_success:
        raise ValueError(f"Hunter connection failed: {r.status_code} {r.text}")
    data = r.json()
    return {"ok": True, "email": data.get("data", {}).get("email")}
