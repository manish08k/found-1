"""Apollo.io Sales Intelligence integration — people/org search, enrichment, contacts, sequences."""
import structlog
import httpx

from core.execution_engine import register_node
from core.ssrf_guard import assert_safe_url
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)

APOLLO_BASE = "https://api.apollo.io/v1"


async def _apollo_key(credential_id: str, db) -> str:
    """Retrieve and decrypt the Apollo api_key."""
    from sqlalchemy import select
    from storage.models import OAuthCredential
    result = await db.execute(select(OAuthCredential).where(OAuthCredential.id == credential_id))
    cred_row = result.scalar_one()
    cred = decrypt_credential(cred_row.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    api_key = cred.get("api_key")
    if not api_key:
        raise ValueError("Apollo credential is missing 'api_key'")
    return api_key


def _apollo_client() -> httpx.AsyncClient:
    """Build an httpx AsyncClient for Apollo (no default auth headers — key goes in body/params)."""
    return httpx.AsyncClient(
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    """Raise a descriptive ValueError on non-2xx responses and return parsed JSON."""
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Apollo API error {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# People search
# ---------------------------------------------------------------------------

@register_node("apollo.search_people")
async def apollo_search_people(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search for people via Apollo's mixed_people/search endpoint."""
    api_key = await _apollo_key(credential_id, db)
    url = f"{APOLLO_BASE}/mixed_people/search"
    assert_safe_url(url)

    body: dict = {"api_key": api_key}

    list_fields = ("person_titles", "person_locations", "organization_num_employees_ranges", "contact_email_status")
    for field in list_fields:
        v = config.get(field)
        if v is not None:
            body[field] = v if isinstance(v, list) else [v]

    per_page = config.get("per_page", 25)
    body["per_page"] = min(int(per_page), 100)
    page = config.get("page", 1)
    body["page"] = int(page)

    async with _apollo_client() as client:
        r = await client.post(url, json=body)
    resp = _check(r)
    return {
        "people": resp.get("people") or [],
        "pagination": resp.get("pagination", {}),
    }


# ---------------------------------------------------------------------------
# Organization search
# ---------------------------------------------------------------------------

@register_node("apollo.search_organizations")
async def apollo_search_organizations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search for organizations via Apollo's mixed_companies/search endpoint."""
    api_key = await _apollo_key(credential_id, db)
    url = f"{APOLLO_BASE}/mixed_companies/search"
    assert_safe_url(url)

    body: dict = {"api_key": api_key}

    list_fields = ("organization_locations", "organization_num_employees_ranges", "organization_industry_tag_ids")
    for field in list_fields:
        v = config.get(field)
        if v is not None:
            body[field] = v if isinstance(v, list) else [v]

    per_page = config.get("per_page", 25)
    body["per_page"] = min(int(per_page), 100)
    page = config.get("page", 1)
    body["page"] = int(page)

    async with _apollo_client() as client:
        r = await client.post(url, json=body)
    resp = _check(r)
    return {
        "organizations": resp.get("organizations") or [],
        "pagination": resp.get("pagination", {}),
    }


# ---------------------------------------------------------------------------
# Person lookup & enrichment
# ---------------------------------------------------------------------------

@register_node("apollo.get_person")
async def apollo_get_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a person record from Apollo by ID."""
    api_key = await _apollo_key(credential_id, db)
    person_id = config.get("person_id")
    if not person_id:
        raise ValueError("apollo.get_person requires 'person_id'")

    url = f"{APOLLO_BASE}/people/{person_id}"
    assert_safe_url(url)

    async with _apollo_client() as client:
        r = await client.get(url, params={"api_key": api_key})
    resp = _check(r)
    return {"person": resp.get("person") or {}}


@register_node("apollo.enrich_person")
async def apollo_enrich_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Enrich a person record via email or name + organization lookup."""
    api_key = await _apollo_key(credential_id, db)
    url = f"{APOLLO_BASE}/people/match"
    assert_safe_url(url)

    body: dict = {"api_key": api_key}

    email = config.get("email")
    if email:
        body["email"] = email
    else:
        first_name = config.get("first_name")
        last_name = config.get("last_name")
        organization_name = config.get("organization_name")
        if not last_name:
            raise ValueError(
                "apollo.enrich_person requires 'email' OR ('first_name', 'last_name', 'organization_name')"
            )
        if first_name:
            body["first_name"] = first_name
        body["last_name"] = last_name
        if organization_name:
            body["organization_name"] = organization_name

    async with _apollo_client() as client:
        r = await client.post(url, json=body)
    resp = _check(r)
    return {"person": resp.get("person") or {}}


# ---------------------------------------------------------------------------
# Organization enrichment
# ---------------------------------------------------------------------------

@register_node("apollo.enrich_organization")
async def apollo_enrich_organization(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Enrich an organization record via domain or company name."""
    api_key = await _apollo_key(credential_id, db)
    url = f"{APOLLO_BASE}/organizations/enrich"
    assert_safe_url(url)

    domain = config.get("domain")
    name = config.get("name")
    if not domain and not name:
        raise ValueError("apollo.enrich_organization requires 'domain' or 'name'")

    body: dict = {"api_key": api_key}
    if domain:
        body["domain"] = domain
    if name:
        body["name"] = name

    async with _apollo_client() as client:
        r = await client.post(url, json=body)
    resp = _check(r)
    return {"organization": resp.get("organization") or {}}


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@register_node("apollo.create_contact")
async def apollo_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact in Apollo."""
    api_key = await _apollo_key(credential_id, db)
    url = f"{APOLLO_BASE}/contacts"
    assert_safe_url(url)

    first_name = config.get("first_name")
    last_name = config.get("last_name")
    if not last_name:
        raise ValueError("apollo.create_contact requires at least 'last_name'")

    body: dict = {"api_key": api_key}
    if first_name:
        body["first_name"] = first_name
    body["last_name"] = last_name

    for field in ("email", "organization_name", "title"):
        v = config.get(field)
        if v is not None:
            body[field] = v

    async with _apollo_client() as client:
        r = await client.post(url, json=body)
    resp = _check(r)
    return {"contact": resp.get("contact") or {}}


@register_node("apollo.update_contact")
async def apollo_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing contact in Apollo."""
    api_key = await _apollo_key(credential_id, db)
    contact_id = config.get("contact_id")
    if not contact_id:
        raise ValueError("apollo.update_contact requires 'contact_id'")

    url = f"{APOLLO_BASE}/contacts/{contact_id}"
    assert_safe_url(url)

    body: dict = {"api_key": api_key}
    for field in ("first_name", "last_name", "email", "organization_name", "title", "phone"):
        v = config.get(field)
        if v is not None:
            body[field] = v

    async with _apollo_client() as client:
        r = await client.put(url, json=body)
    resp = _check(r)
    return {"contact": resp.get("contact") or {}}


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

@register_node("apollo.add_to_sequence")
async def apollo_add_to_sequence(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add one or more contacts to an Apollo email sequence."""
    api_key = await _apollo_key(credential_id, db)
    sequence_id = config.get("sequence_id")
    contact_ids = config.get("contact_ids")
    if not sequence_id:
        raise ValueError("apollo.add_to_sequence requires 'sequence_id'")
    if not contact_ids:
        raise ValueError("apollo.add_to_sequence requires 'contact_ids' (list)")
    if isinstance(contact_ids, str):
        contact_ids = [contact_ids]

    url = f"{APOLLO_BASE}/emailer_campaigns/{sequence_id}/add_contact_ids"
    assert_safe_url(url)

    body: dict = {
        "api_key": api_key,
        "contact_ids": contact_ids,
    }
    send_from = config.get("send_email_from_email_account_id")
    if send_from:
        body["send_email_from_email_account_id"] = send_from

    async with _apollo_client() as client:
        r = await client.post(url, json=body)
    resp = _check(r)
    return {
        "contacts": resp.get("contacts") or [],
        "emailer_campaign": resp.get("emailer_campaign") or {},
    }


# ---------------------------------------------------------------------------
# Email accounts
# ---------------------------------------------------------------------------

@register_node("apollo.get_email_accounts")
async def apollo_get_email_accounts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all connected email accounts in Apollo."""
    api_key = await _apollo_key(credential_id, db)
    url = f"{APOLLO_BASE}/email_accounts"
    assert_safe_url(url)

    async with _apollo_client() as client:
        r = await client.get(url, params={"api_key": api_key})
    resp = _check(r)
    return {"email_accounts": resp.get("email_accounts") or []}
