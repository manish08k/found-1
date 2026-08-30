"""Pipedrive CRM integration — deals, persons, organizations, activities, notes, pipelines."""
import structlog
import httpx

from core.execution_engine import register_node
from core.ssrf_guard import assert_safe_url
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)

PD_BASE = "https://api.pipedrive.com/v1"


async def _pd_token(credential_id: str, db) -> str:
    """Retrieve and decrypt the Pipedrive api_token."""
    from sqlalchemy import select
    from storage.models import OAuthCredential
    result = await db.execute(select(OAuthCredential).where(OAuthCredential.id == credential_id))
    cred_row = result.scalar_one()
    cred = decrypt_credential(cred_row.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    token = cred.get("api_token")
    if not token:
        raise ValueError("Pipedrive credential is missing 'api_token'")
    return token


def _pd_client(api_token: str) -> httpx.AsyncClient:
    """Build an httpx AsyncClient with the Pipedrive api_token as a default query param."""
    return httpx.AsyncClient(
        params={"api_token": api_token},
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
        raise ValueError(f"Pipedrive API error {r.status_code}: {detail}")
    return r.json()


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

@register_node("pipedrive.create_deal")
async def pd_create_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new deal in Pipedrive."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/deals"
    assert_safe_url(url)

    body = {}
    for field in ("title", "value", "currency", "person_id", "org_id", "pipeline_id", "stage_id", "status"):
        v = config.get(field)
        if v is not None:
            body[field] = v

    if not body.get("title"):
        raise ValueError("pipedrive.create_deal requires 'title'")

    async with _pd_client(token) as client:
        r = await client.post(url, json=body)
    data = _check(r)
    return {"deal": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.get_deal")
async def pd_get_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a single deal by ID."""
    token = await _pd_token(credential_id, db)
    deal_id = config.get("deal_id")
    if not deal_id:
        raise ValueError("pipedrive.get_deal requires 'deal_id'")

    url = f"{PD_BASE}/deals/{deal_id}"
    assert_safe_url(url)

    async with _pd_client(token) as client:
        r = await client.get(url)
    data = _check(r)
    return {"deal": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.update_deal")
async def pd_update_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing deal."""
    token = await _pd_token(credential_id, db)
    deal_id = config.get("deal_id")
    if not deal_id:
        raise ValueError("pipedrive.update_deal requires 'deal_id'")

    url = f"{PD_BASE}/deals/{deal_id}"
    assert_safe_url(url)

    body = {k: v for k, v in config.items()
            if k != "deal_id" and v is not None}

    async with _pd_client(token) as client:
        r = await client.put(url, json=body)
    data = _check(r)
    return {"deal": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.list_deals")
async def pd_list_deals(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List deals with optional status filter."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/deals"
    assert_safe_url(url)

    params: dict = {}
    status = config.get("status", "all")
    if status:
        params["status"] = status
    limit = config.get("limit", 100)
    params["limit"] = min(int(limit), 500)

    async with _pd_client(token) as client:
        r = await client.get(url, params=params)
    data = _check(r)
    deals = data.get("data") or []
    pagination = data.get("additional_data", {}).get("pagination", {})
    return {"deals": deals, "total": pagination.get("total_size", len(deals))}


@register_node("pipedrive.search_deals")
async def pd_search_deals(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Full-text search across deals."""
    token = await _pd_token(credential_id, db)
    term = config.get("term")
    if not term:
        raise ValueError("pipedrive.search_deals requires 'term'")

    url = f"{PD_BASE}/deals/search"
    assert_safe_url(url)

    params: dict = {"term": term}
    fields = config.get("fields", "title")
    if fields:
        params["fields"] = fields

    async with _pd_client(token) as client:
        r = await client.get(url, params=params)
    data = _check(r)
    items = (data.get("data") or {}).get("items", [])
    return {"deals": [i.get("item") for i in items], "total": len(items)}


@register_node("pipedrive.delete_deal")
async def pd_delete_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a deal permanently."""
    token = await _pd_token(credential_id, db)
    deal_id = config.get("deal_id")
    if not deal_id:
        raise ValueError("pipedrive.delete_deal requires 'deal_id'")

    url = f"{PD_BASE}/deals/{deal_id}"
    assert_safe_url(url)

    async with _pd_client(token) as client:
        r = await client.delete(url)
    data = _check(r)
    return {"deleted_id": data.get("data", {}).get("id"), "success": data.get("success")}


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------

@register_node("pipedrive.create_person")
async def pd_create_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new person (contact) in Pipedrive."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/persons"
    assert_safe_url(url)

    name = config.get("name")
    if not name:
        raise ValueError("pipedrive.create_person requires 'name'")

    body: dict = {"name": name}
    email = config.get("email")
    if email:
        body["email"] = [{"value": email, "primary": True}] if isinstance(email, str) else email
    phone = config.get("phone")
    if phone:
        body["phone"] = [{"value": phone, "primary": True}] if isinstance(phone, str) else phone
    org_id = config.get("org_id")
    if org_id is not None:
        body["org_id"] = org_id

    async with _pd_client(token) as client:
        r = await client.post(url, json=body)
    data = _check(r)
    return {"person": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.get_person")
async def pd_get_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a person by ID."""
    token = await _pd_token(credential_id, db)
    person_id = config.get("person_id")
    if not person_id:
        raise ValueError("pipedrive.get_person requires 'person_id'")

    url = f"{PD_BASE}/persons/{person_id}"
    assert_safe_url(url)

    async with _pd_client(token) as client:
        r = await client.get(url)
    data = _check(r)
    return {"person": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.update_person")
async def pd_update_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Update an existing person."""
    token = await _pd_token(credential_id, db)
    person_id = config.get("person_id")
    if not person_id:
        raise ValueError("pipedrive.update_person requires 'person_id'")

    url = f"{PD_BASE}/persons/{person_id}"
    assert_safe_url(url)

    body = {k: v for k, v in config.items()
            if k != "person_id" and v is not None}

    async with _pd_client(token) as client:
        r = await client.put(url, json=body)
    data = _check(r)
    return {"person": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.list_persons")
async def pd_list_persons(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List persons (contacts) in the CRM."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/persons"
    assert_safe_url(url)

    limit = config.get("limit", 100)
    params = {"limit": min(int(limit), 500)}

    async with _pd_client(token) as client:
        r = await client.get(url, params=params)
    data = _check(r)
    persons = data.get("data") or []
    pagination = data.get("additional_data", {}).get("pagination", {})
    return {"persons": persons, "total": pagination.get("total_size", len(persons))}


@register_node("pipedrive.search_persons")
async def pd_search_persons(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search for persons by term."""
    token = await _pd_token(credential_id, db)
    term = config.get("term")
    if not term:
        raise ValueError("pipedrive.search_persons requires 'term'")

    url = f"{PD_BASE}/persons/search"
    assert_safe_url(url)

    async with _pd_client(token) as client:
        r = await client.get(url, params={"term": term})
    data = _check(r)
    items = (data.get("data") or {}).get("items", [])
    return {"persons": [i.get("item") for i in items], "total": len(items)}


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

@register_node("pipedrive.create_organization")
async def pd_create_organization(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new organization in Pipedrive."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/organizations"
    assert_safe_url(url)

    name = config.get("name")
    if not name:
        raise ValueError("pipedrive.create_organization requires 'name'")

    body: dict = {"name": name}
    address = config.get("address")
    if address:
        body["address"] = address

    async with _pd_client(token) as client:
        r = await client.post(url, json=body)
    data = _check(r)
    return {"organization": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.get_organization")
async def pd_get_organization(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve an organization by ID."""
    token = await _pd_token(credential_id, db)
    org_id = config.get("org_id")
    if not org_id:
        raise ValueError("pipedrive.get_organization requires 'org_id'")

    url = f"{PD_BASE}/organizations/{org_id}"
    assert_safe_url(url)

    async with _pd_client(token) as client:
        r = await client.get(url)
    data = _check(r)
    return {"organization": data.get("data"), "success": data.get("success")}


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@register_node("pipedrive.create_activity")
async def pd_create_activity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new activity (call, email, meeting, etc.) in Pipedrive."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/activities"
    assert_safe_url(url)

    subject = config.get("subject")
    if not subject:
        raise ValueError("pipedrive.create_activity requires 'subject'")

    body: dict = {"subject": subject}
    for field in ("type", "deal_id", "person_id", "due_date", "due_time", "note"):
        v = config.get(field)
        if v is not None:
            body[field] = v

    async with _pd_client(token) as client:
        r = await client.post(url, json=body)
    data = _check(r)
    return {"activity": data.get("data"), "success": data.get("success")}


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@register_node("pipedrive.create_note")
async def pd_create_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a note attached to a deal, person, or organization."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/notes"
    assert_safe_url(url)

    content = config.get("content")
    if not content:
        raise ValueError("pipedrive.create_note requires 'content'")

    body: dict = {"content": content}
    for field in ("deal_id", "person_id", "org_id"):
        v = config.get(field)
        if v is not None:
            body[field] = v

    async with _pd_client(token) as client:
        r = await client.post(url, json=body)
    data = _check(r)
    return {"note": data.get("data"), "success": data.get("success")}


# ---------------------------------------------------------------------------
# Pipeline / Stages
# ---------------------------------------------------------------------------

@register_node("pipedrive.add_deal_to_pipeline")
async def pd_add_deal_to_pipeline(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Move a deal to a specific pipeline and stage."""
    token = await _pd_token(credential_id, db)
    deal_id = config.get("deal_id")
    if not deal_id:
        raise ValueError("pipedrive.add_deal_to_pipeline requires 'deal_id'")

    url = f"{PD_BASE}/deals/{deal_id}"
    assert_safe_url(url)

    body: dict = {}
    pipeline_id = config.get("pipeline_id")
    stage_id = config.get("stage_id")
    if pipeline_id is not None:
        body["pipeline_id"] = pipeline_id
    if stage_id is not None:
        body["stage_id"] = stage_id

    if not body:
        raise ValueError("pipedrive.add_deal_to_pipeline requires 'pipeline_id' and/or 'stage_id'")

    async with _pd_client(token) as client:
        r = await client.put(url, json=body)
    data = _check(r)
    return {"deal": data.get("data"), "success": data.get("success")}


@register_node("pipedrive.get_pipeline_stages")
async def pd_get_pipeline_stages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve all stages for a given pipeline."""
    token = await _pd_token(credential_id, db)
    url = f"{PD_BASE}/stages"
    assert_safe_url(url)

    params: dict = {}
    pipeline_id = config.get("pipeline_id")
    if pipeline_id is not None:
        params["pipeline_id"] = pipeline_id

    async with _pd_client(token) as client:
        r = await client.get(url, params=params)
    data = _check(r)
    return {"stages": data.get("data") or [], "success": data.get("success")}
