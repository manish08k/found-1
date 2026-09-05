"""
Keap (formerly Infusionsoft) CRM integration.

Provides contact management, order creation, and tagging via the Keap REST API v1.

Credential fields:
  - access_token : OAuth2 Bearer token
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.infusionsoft.com/crm/rest/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Keap credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
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
        raise ValueError(f"Keap API error {r.status_code}: {detail}")


@register_node("keap.list_contacts")
async def keap_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List contacts from Keap CRM."""
    limit = min(int(config.get("limit") or input_data.get("limit", 20)), 1000)
    offset = int(config.get("offset") or input_data.get("offset", 0))
    email = config.get("email") or input_data.get("email")

    params: dict = {"limit": limit, "offset": offset}
    if email:
        params["email"] = email

    log.info("keap.list_contacts", limit=limit, offset=offset)
    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"contacts": data.get("contacts", []), "count": data.get("count", 0)}


@register_node("keap.create_contact")
async def keap_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new contact in Keap CRM."""
    email = config.get("email") or input_data.get("email")
    first_name = config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    phone = config.get("phone") or input_data.get("phone", "")

    if not email:
        raise ValueError("keap.create_contact requires 'email'")

    payload: dict = {
        "email_addresses": [{"email": email, "field": "EMAIL1"}],
    }
    if first_name:
        payload["given_name"] = first_name
    if last_name:
        payload["family_name"] = last_name
    if phone:
        payload["phone_numbers"] = [{"number": phone, "field": "PHONE1"}]

    log.info("keap.create_contact", email=email)
    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts", json=payload)
        _raise_for_status(r)
        contact = r.json()

    return {"contact": contact, "contact_id": contact.get("id")}


@register_node("keap.create_order")
async def keap_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new order in Keap."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    title = config.get("title") or input_data.get("title", "Order")
    order_date = config.get("order_date") or input_data.get("order_date")
    order_items = config.get("order_items") or input_data.get("order_items", [])

    if not contact_id:
        raise ValueError("keap.create_order requires 'contact_id'")

    payload: dict = {
        "contact_id": int(contact_id),
        "title": title,
        "order_items": order_items,
    }
    if order_date:
        payload["order_date"] = order_date

    log.info("keap.create_order", contact_id=contact_id, title=title)
    async with await _client(credential_id, db) as client:
        r = await client.post("/orders", json=payload)
        _raise_for_status(r)
        order = r.json()

    return {"order": order, "order_id": order.get("id")}


@register_node("keap.add_tag")
async def keap_add_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Apply a tag to a contact in Keap."""
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    tag_id = config.get("tag_id") or input_data.get("tag_id")

    if not contact_id:
        raise ValueError("keap.add_tag requires 'contact_id'")
    if not tag_id:
        raise ValueError("keap.add_tag requires 'tag_id'")

    log.info("keap.add_tag", contact_id=contact_id, tag_id=tag_id)
    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/contacts/{contact_id}/tags",
            json={"tagIds": [int(tag_id)]},
        )
        _raise_for_status(r)

    return {"tagged": True, "contact_id": contact_id, "tag_id": tag_id}
