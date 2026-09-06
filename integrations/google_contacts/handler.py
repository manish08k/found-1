"""Google Contacts integration — contact management via People API."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)
BASE = "https://people.googleapis.com/v1"


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("google_contacts.list_contacts")
async def google_contacts_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    headers = await _headers(credential_id, db)
    page_size = config.get("page_size", 20)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/people/me/connections",
                             params={"personFields": "names,emailAddresses,phoneNumbers", "pageSize": page_size})
        r.raise_for_status()
    data = r.json()
    return {"contacts": data.get("connections", []), "total": data.get("totalItems", 0)}


@register_node("google_contacts.create_contact")
async def google_contacts_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(f"{BASE}/people:createContact", json={
            "names": [{"givenName": merged.get("first_name", ""), "familyName": merged.get("last_name", "")}],
            "emailAddresses": [{"value": merged.get("email", "")}] if merged.get("email") else [],
            "phoneNumbers": [{"value": merged.get("phone", "")}] if merged.get("phone") else [],
        })
        r.raise_for_status()
    return r.json()


@register_node("google_contacts.search_contacts")
async def google_contacts_search_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    headers = await _headers(credential_id, db)
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(f"{BASE}/people:searchContacts",
                             params={"query": merged.get("query", ""), "readMask": "names,emailAddresses"})
        r.raise_for_status()
    return {"results": r.json().get("results", [])}
