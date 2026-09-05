"""
Affinity relationship intelligence CRM integration.

Provides person and organization lookup, creation, and list entry
management via the Affinity API.

Credential fields:
  - api_key : Affinity API key

Auth: HTTP Basic with empty username and api_key as password.
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.affinity.co"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Affinity credential missing 'api_key'")

    # Affinity uses Basic auth with empty username
    token = base64.b64encode(f":{api_key}".encode()).decode()
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Basic {token}",
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
        raise ValueError(f"Affinity API error {r.status_code}: {detail}")


@register_node("affinity.list_persons")
async def af_list_persons(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search and list persons in Affinity."""
    term = config.get("term") or input_data.get("term", "")
    with_interaction_dates = config.get("with_interaction_dates") or input_data.get("with_interaction_dates", False)
    page_size = int(config.get("page_size") or input_data.get("page_size", 25))
    page_token = config.get("page_token") or input_data.get("page_token")

    params: dict = {"page_size": page_size}
    if term:
        params["term"] = term
    if with_interaction_dates:
        params["with_interaction_dates"] = "true"
    if page_token:
        params["page_token"] = page_token

    async with await _client(credential_id, db) as client:
        r = await client.get("/persons", params=params)
        _raise_for_status(r)
        data = r.json()

    persons = data.get("persons", [])
    return {
        "persons": persons,
        "count": len(persons),
        "next_page_token": data.get("next_page_token"),
    }


@register_node("affinity.create_person")
async def af_create_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new person record in Affinity."""
    first_name = config.get("first_name") or input_data.get("first_name")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    emails = config.get("emails") or input_data.get("emails", [])

    if not first_name:
        raise ValueError("affinity.create_person requires 'first_name'")

    # emails can be a comma-separated string or a list
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]

    payload: dict = {"first_name": first_name, "last_name": last_name, "emails": emails}

    # Optional organization associations
    org_ids = config.get("organization_ids") or input_data.get("organization_ids", [])
    if isinstance(org_ids, (int, str)):
        org_ids = [int(org_ids)]
    if org_ids:
        payload["organization_ids"] = [int(i) for i in org_ids]

    async with await _client(credential_id, db) as client:
        r = await client.post("/persons", json=payload)
        _raise_for_status(r)
        person = r.json()

    log.info("affinity.create_person", person_id=person.get("id"), first_name=first_name)
    return {"person": person, "person_id": person.get("id")}


@register_node("affinity.list_organizations")
async def af_list_organizations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search and list organizations in Affinity."""
    term = config.get("term") or input_data.get("term", "")
    page_size = int(config.get("page_size") or input_data.get("page_size", 25))
    page_token = config.get("page_token") or input_data.get("page_token")
    with_interaction_dates = config.get("with_interaction_dates") or input_data.get("with_interaction_dates", False)

    params: dict = {"page_size": page_size}
    if term:
        params["term"] = term
    if with_interaction_dates:
        params["with_interaction_dates"] = "true"
    if page_token:
        params["page_token"] = page_token

    async with await _client(credential_id, db) as client:
        r = await client.get("/organizations", params=params)
        _raise_for_status(r)
        data = r.json()

    organizations = data.get("organizations", [])
    return {
        "organizations": organizations,
        "count": len(organizations),
        "next_page_token": data.get("next_page_token"),
    }


@register_node("affinity.create_list_entry")
async def af_create_list_entry(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add a person or organization to an Affinity list."""
    list_id = config.get("list_id") or input_data.get("list_id")
    entity_id = config.get("entity_id") or input_data.get("entity_id")

    if not list_id:
        raise ValueError("affinity.create_list_entry requires 'list_id'")
    if not entity_id:
        raise ValueError("affinity.create_list_entry requires 'entity_id'")

    payload: dict = {"entity_id": int(entity_id)}

    # Optional: creator person ID
    creator_id = config.get("creator_id") or input_data.get("creator_id")
    if creator_id:
        payload["creator_id"] = int(creator_id)

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/lists/{list_id}/list-entries", json=payload)
        _raise_for_status(r)
        entry = r.json()

    log.info("affinity.create_list_entry", list_id=list_id, entity_id=entity_id, entry_id=entry.get("id"))
    return {"list_entry": entry, "entry_id": entry.get("id")}


@register_node("affinity.get_lists")
async def af_get_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve all lists available in the Affinity account."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/lists")
        _raise_for_status(r)
        lists = r.json()

    return {"lists": lists, "count": len(lists) if isinstance(lists, list) else 0}
