"""HubSpot CRM integration — contacts, deals, companies, emails + polling."""
import structlog
import httpx

from core.execution_engine import register_node
from triggers.engine import register_poller
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)

HS_BASE = "https://api.hubapi.com"


async def _hs(credential_id: str, db) -> httpx.AsyncClient:
    token = await get_access_token(credential_id, db)
    return httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )


@register_node("hubspot.create_contact")
async def hs_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    properties = config.get("properties") or input_data.get("properties", {})

    async with await _hs(credential_id, db) as client:
        r = await client.post(f"{HS_BASE}/crm/v3/objects/contacts",
                              json={"properties": properties})
        r.raise_for_status()
        data = r.json()
    return {"contact_id": data["id"], "properties": data["properties"]}


@register_node("hubspot.update_contact")
async def hs_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    properties = config.get("properties") or input_data.get("properties", {})

    async with await _hs(credential_id, db) as client:
        r = await client.patch(f"{HS_BASE}/crm/v3/objects/contacts/{contact_id}",
                               json={"properties": properties})
        r.raise_for_status()
        data = r.json()
    return {"contact_id": data["id"]}


@register_node("hubspot.get_contact")
async def hs_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    email = config.get("email") or input_data.get("email")
    properties = config.get("properties", ["firstname", "lastname", "email", "phone"])

    async with await _hs(credential_id, db) as client:
        if email:
            r = await client.get(f"{HS_BASE}/crm/v3/objects/contacts/{email}",
                                 params={"idProperty": "email", "properties": ",".join(properties)})
        else:
            r = await client.get(f"{HS_BASE}/crm/v3/objects/contacts/{contact_id}",
                                 params={"properties": ",".join(properties)})
        r.raise_for_status()
        data = r.json()
    return {"contact_id": data["id"], "properties": data["properties"]}


@register_node("hubspot.create_deal")
async def hs_create_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    properties = config.get("properties") or input_data.get("properties", {})
    associations = config.get("associations") or input_data.get("associations", [])

    body = {"properties": properties}
    if associations:
        body["associations"] = associations

    async with await _hs(credential_id, db) as client:
        r = await client.post(f"{HS_BASE}/crm/v3/objects/deals", json=body)
        r.raise_for_status()
        data = r.json()
    return {"deal_id": data["id"], "properties": data["properties"]}


@register_node("hubspot.update_deal")
async def hs_update_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    deal_id = config.get("deal_id") or input_data.get("deal_id")
    properties = config.get("properties") or input_data.get("properties", {})

    async with await _hs(credential_id, db) as client:
        r = await client.patch(f"{HS_BASE}/crm/v3/objects/deals/{deal_id}",
                               json={"properties": properties})
        r.raise_for_status()
        data = r.json()
    return {"deal_id": data["id"]}


@register_node("hubspot.search_contacts")
async def hs_search_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    filters = config.get("filters") or input_data.get("filters", [])
    properties = config.get("properties", ["firstname", "lastname", "email"])
    limit = config.get("limit", 10)

    body = {
        "filterGroups": [{"filters": filters}],
        "properties": properties,
        "limit": limit,
    }

    async with await _hs(credential_id, db) as client:
        r = await client.post(f"{HS_BASE}/crm/v3/objects/contacts/search", json=body)
        r.raise_for_status()
        data = r.json()
    return {"contacts": data.get("results", []), "total": data.get("total")}


@register_node("hubspot.create_note")
async def hs_create_note(config: dict, input_data: dict, credential_id: str, db) -> dict:
    body_text = config.get("note_body") or input_data.get("note_body", "")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    deal_id = config.get("deal_id") or input_data.get("deal_id")
    import time

    properties = {
        "hs_note_body": body_text,
        "hs_timestamp": str(int(time.time() * 1000)),
    }
    associations = []
    if contact_id:
        associations.append({"to": {"id": contact_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]})
    if deal_id:
        associations.append({"to": {"id": deal_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 214}]})

    async with await _hs(credential_id, db) as client:
        r = await client.post(f"{HS_BASE}/crm/v3/objects/notes",
                              json={"properties": properties, "associations": associations})
        r.raise_for_status()
        data = r.json()
    return {"note_id": data["id"]}


@register_node("hubspot.send_email")
async def hs_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email_id = config.get("email_id") or input_data.get("email_id")
    contact_ids = config.get("contact_ids") or input_data.get("contact_ids", [])

    async with await _hs(credential_id, db) as client:
        r = await client.post(f"{HS_BASE}/marketing/v3/emails/{email_id}/send",
                              json={"contactIds": contact_ids})
        r.raise_for_status()
    return {"ok": True}


# ─── Polling ──────────────────────────────────────────────────────────────────

_hs_seen: dict[str, set] = {}


@register_poller("hubspot", "new_contact")
async def poll_hubspot_new_contact(config: dict, credential_id: str, db) -> list[dict]:
    key = f"{credential_id}:contacts"
    if key not in _hs_seen:
        _hs_seen[key] = set()

    try:
        async with await _hs(credential_id, db) as client:
            r = await client.get(f"{HS_BASE}/crm/v3/objects/contacts",
                                 params={"limit": 20, "properties": "firstname,lastname,email",
                                         "sort": "-createdate"})
            r.raise_for_status()
            data = r.json()

        new_items = []
        for c in data.get("results", []):
            if c["id"] not in _hs_seen[key]:
                new_items.append(c)
                _hs_seen[key].add(c["id"])
        return new_items
    except Exception as e:
        log.error("hubspot_poll_error", error=str(e))
        return []
