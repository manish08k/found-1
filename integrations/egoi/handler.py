"""
E-goi email/SMS marketing integration.

Provides contact list management, contact creation, email campaign dispatch,
and subscriber querying via the E-goi REST API v3.

Credential fields:
  - api_key : E-goi API key (sent as `Apikey` header)

Base URL: https://api.egoiapp.com/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.egoiapp.com"


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"E-goi API error {r.status_code}: {detail}")


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key", "").strip()
    if not api_key:
        raise ValueError("E-goi credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Apikey": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


@register_node("egoi.get_lists")
async def get_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve all contact lists in the E-goi account.

    Config / input keys:
      - offset (int): Pagination offset. Default 0.
      - limit  (int): Max results (1-100). Default 10.

    Returns:
      { "lists": [...], "total": int }
    """
    offset = int(config.get("offset") or input_data.get("offset", 0))
    limit = min(int(config.get("limit") or input_data.get("limit", 10)), 100)

    log.info("egoi.get_lists", offset=offset, limit=limit)

    async with await _client(credential_id, db) as client:
        r = await client.get("/lists", params={"offset": offset, "count": limit})
        _raise_for_status(r)
        data = r.json()

    items = data.get("items", data if isinstance(data, list) else [])
    return {
        "lists": items,
        "total": data.get("total_items", len(items)),
        "offset": offset,
        "limit": limit,
    }


@register_node("egoi.add_contact")
async def add_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Add a new contact to an E-goi list.

    Config / input keys:
      - list_id    (int|str) : Required. Target list ID.
      - email      (str)     : Contact email address.
      - first_name (str)     : Contact first name.
      - last_name  (str)     : Contact last name.
      - phone      (str)     : Contact phone (E.164 format recommended).
      - cellphone  (str)     : Mobile number.
      - tags       (list)    : List of tag IDs to assign.

    Returns:
      { "contact_id": str, "status": str }
    """
    list_id = config.get("list_id") or input_data.get("list_id")
    if not list_id:
        raise ValueError("egoi.add_contact requires 'list_id'")

    email = config.get("email") or input_data.get("email", "")
    first_name = config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    phone = config.get("phone") or input_data.get("phone", "")
    cellphone = config.get("cellphone") or input_data.get("cellphone", "")
    tags = config.get("tags") or input_data.get("tags", [])

    base: dict = {}
    if email:
        base["email"] = email
    if first_name:
        base["first_name"] = first_name
    if last_name:
        base["last_name"] = last_name
    if phone:
        base["phone"] = phone
    if cellphone:
        base["cellphone"] = cellphone
    if tags:
        base["tags"] = tags if isinstance(tags, list) else [tags]

    payload = {"base": base}

    log.info("egoi.add_contact", list_id=list_id, email=email)

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/lists/{list_id}/contacts", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "contact_id": data.get("contact_id", data.get("id")),
        "status": data.get("status", "created"),
        "raw": data,
    }


@register_node("egoi.send_email_campaign")
async def send_email_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Schedule or immediately send an email campaign.

    Config / input keys:
      - list_id           (int|str) : Required. Recipient list ID.
      - campaign_hash     (str)     : Required. Existing campaign hash/ID.
      - schedule_date     (str)     : ISO-8601 datetime to send. Omit for immediate.
      - sender_id         (int)     : Sender ID configured in E-goi account.
      - segment_id        (int)     : Optional segment to restrict recipients.

    Returns:
      { "campaign_hash": str, "scheduled": bool, "send_date": str }
    """
    list_id = config.get("list_id") or input_data.get("list_id")
    campaign_hash = config.get("campaign_hash") or input_data.get("campaign_hash")

    if not list_id:
        raise ValueError("egoi.send_email_campaign requires 'list_id'")
    if not campaign_hash:
        raise ValueError("egoi.send_email_campaign requires 'campaign_hash'")

    schedule_date = config.get("schedule_date") or input_data.get("schedule_date")
    sender_id = config.get("sender_id") or input_data.get("sender_id")
    segment_id = config.get("segment_id") or input_data.get("segment_id")

    payload: dict = {
        "list_id": int(list_id),
    }
    if schedule_date:
        payload["schedule_date"] = schedule_date
    if sender_id:
        payload["sender_id"] = int(sender_id)
    if segment_id:
        payload["segments"] = {"type": "id", "id": int(segment_id)}

    log.info("egoi.send_email_campaign", list_id=list_id, campaign_hash=campaign_hash)

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/campaigns/email/{campaign_hash}/actions/send",
            json=payload,
        )
        _raise_for_status(r)
        data = r.json()

    return {
        "campaign_hash": campaign_hash,
        "scheduled": bool(schedule_date),
        "send_date": schedule_date or "immediate",
        "raw": data,
    }


@register_node("egoi.get_subscribers")
async def get_subscribers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve subscribers from a specific E-goi list.

    Config / input keys:
      - list_id (int|str) : Required. List to query.
      - status  (str)     : Filter by status: "active", "inactive",
                            "removed", "unsubscribed". Default "active".
      - offset  (int)     : Pagination offset. Default 0.
      - limit   (int)     : Max records (1-1000). Default 50.
      - email   (str)     : Optional email filter.

    Returns:
      { "contacts": [...], "total": int }
    """
    list_id = config.get("list_id") or input_data.get("list_id")
    if not list_id:
        raise ValueError("egoi.get_subscribers requires 'list_id'")

    status = config.get("status") or input_data.get("status", "active")
    offset = int(config.get("offset") or input_data.get("offset", 0))
    limit = min(int(config.get("limit") or input_data.get("limit", 50)), 1000)
    email_filter = config.get("email") or input_data.get("email")

    params: dict = {"status": status, "offset": offset, "count": limit}
    if email_filter:
        params["email"] = email_filter

    log.info("egoi.get_subscribers", list_id=list_id, status=status)

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/lists/{list_id}/contacts", params=params)
        _raise_for_status(r)
        data = r.json()

    items = data.get("items", data if isinstance(data, list) else [])
    return {
        "contacts": items,
        "total": data.get("total_items", len(items)),
        "offset": offset,
        "limit": limit,
        "status": status,
    }
