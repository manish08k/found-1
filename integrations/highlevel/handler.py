"""HighLevel CRM/marketing integration — contacts, opportunities, SMS."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

HL_BASE = "https://rest.gohighlevel.com/v1/"


async def _hl_client(credential_id: str, db) -> httpx.AsyncClient:
    """Build an authenticated HighLevel AsyncClient.

    Credential fields:
      api_key — HighLevel API key
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")
    return httpx.AsyncClient(
        base_url=HL_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )


@register_node("highlevel.list_contacts")
async def hl_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List contacts in a HighLevel location/sub-account.

    config:
      location_id — HighLevel location ID (required)
      query       — search query string (optional)
      limit       — max contacts to return (default 20, max 100)
      start_after — pagination cursor (contact ID to start after, optional)
      tags        — list of tags to filter by (optional)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")

    location_id = config.get("location_id") or input_data.get("location_id")
    if not location_id:
        raise ValueError("location_id is required for highlevel.list_contacts")

    params: dict = {
        "locationId": location_id,
        "limit": min(int(config.get("limit", 20)), 100),
    }
    query = config.get("query") or input_data.get("query")
    start_after = config.get("start_after") or input_data.get("start_after")
    tags = config.get("tags") or input_data.get("tags", [])

    if query:
        params["query"] = query
    if start_after:
        params["startAfter"] = start_after
    if tags:
        params["tags"] = ",".join(tags) if isinstance(tags, list) else tags

    async with httpx.AsyncClient(
        base_url=HL_BASE,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get("contacts/", params=params)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("contacts", [])
    log.info("highlevel.list_contacts", location_id=location_id, count=len(contacts))
    return {
        "contacts": contacts,
        "count": len(contacts),
        "meta": data.get("meta", {}),
        "location_id": location_id,
    }


@register_node("highlevel.create_contact")
async def hl_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new HighLevel contact.

    config/input_data:
      location_id — HighLevel location ID (required)
      first_name  — contact first name
      last_name   — contact last name
      email       — contact email address
      phone       — contact phone number (E.164 format preferred)
      tags        — list of tags (optional)
      source      — lead source string (optional)
      custom_field — list of {id, field_value} dicts (optional)
      address1    — street address (optional)
      city        — city (optional)
      state       — state (optional)
      country     — country code (optional)
      postal_code — postal/zip code (optional)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")

    location_id = config.get("location_id") or input_data.get("location_id")
    if not location_id:
        raise ValueError("location_id is required for highlevel.create_contact")

    payload: dict = {"locationId": location_id}
    field_map = {
        "first_name": "firstName",
        "last_name": "lastName",
        "email": "email",
        "phone": "phone",
        "tags": "tags",
        "source": "source",
        "address1": "address1",
        "city": "city",
        "state": "state",
        "country": "country",
        "postal_code": "postalCode",
        "custom_field": "customField",
    }
    for key, api_key_name in field_map.items():
        val = config.get(key) or input_data.get(key)
        if val is not None:
            payload[api_key_name] = val

    async with httpx.AsyncClient(
        base_url=HL_BASE,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post("contacts/", json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("contact", data)
    contact_id = contact.get("id")
    log.info("highlevel.create_contact", contact_id=contact_id, location_id=location_id)
    return {
        "contact_id": contact_id,
        "contact": contact,
        "location_id": location_id,
    }


@register_node("highlevel.create_opportunity")
async def hl_create_opportunity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create an opportunity in a HighLevel pipeline.

    config/input_data:
      pipeline_id  — pipeline ID (required)
      location_id  — location ID (required)
      stage_id     — pipeline stage ID (required)
      contact_id   — associated contact ID (required)
      name         — opportunity name (required)
      status       — open | won | lost | abandoned (default 'open')
      monetary_value — deal value in cents (optional)
      assigned_to  — user ID to assign to (optional)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")

    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")
    location_id = config.get("location_id") or input_data.get("location_id")
    stage_id = config.get("stage_id") or input_data.get("stage_id")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    name = config.get("name") or input_data.get("name", "New Opportunity")

    for field, val in [("pipeline_id", pipeline_id), ("location_id", location_id),
                       ("stage_id", stage_id), ("contact_id", contact_id)]:
        if not val:
            raise ValueError(f"{field} is required for highlevel.create_opportunity")

    payload: dict = {
        "pipelineId": pipeline_id,
        "locationId": location_id,
        "stageId": stage_id,
        "contactId": contact_id,
        "name": name,
        "status": config.get("status") or input_data.get("status", "open"),
    }

    monetary_value = config.get("monetary_value") or input_data.get("monetary_value")
    assigned_to = config.get("assigned_to") or input_data.get("assigned_to")
    if monetary_value is not None:
        payload["monetaryValue"] = int(monetary_value)
    if assigned_to:
        payload["assignedTo"] = assigned_to

    async with httpx.AsyncClient(
        base_url=HL_BASE,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post("opportunities/", json=payload)
        r.raise_for_status()
        data = r.json()

    opportunity = data.get("opportunity", data)
    opp_id = opportunity.get("id")
    log.info("highlevel.create_opportunity", opportunity_id=opp_id, pipeline_id=pipeline_id)
    return {
        "opportunity_id": opp_id,
        "opportunity": opportunity,
        "pipeline_id": pipeline_id,
        "stage_id": stage_id,
    }


@register_node("highlevel.send_sms")
async def hl_send_sms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send an SMS message to a HighLevel contact.

    config/input_data:
      type           — message type (default 'SMS')
      contact_id     — recipient contact ID (required)
      from_number    — sender phone number in E.164 format (required)
      message        — SMS message body (required)
      scheduled_timestamp — epoch seconds to schedule message (optional)
    """
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("token", "")

    contact_id = config.get("contact_id") or input_data.get("contact_id")
    from_number = config.get("from_number") or input_data.get("from_number")
    message = config.get("message") or input_data.get("message", "")

    if not contact_id or not from_number:
        raise ValueError("contact_id and from_number are required for highlevel.send_sms")
    if not message:
        raise ValueError("message cannot be empty for highlevel.send_sms")

    payload: dict = {
        "type": config.get("type") or input_data.get("type", "SMS"),
        "contactId": contact_id,
        "fromNumber": from_number,
        "message": message,
    }

    scheduled_ts = config.get("scheduled_timestamp") or input_data.get("scheduled_timestamp")
    if scheduled_ts:
        payload["scheduledTimestamp"] = int(scheduled_ts)

    async with httpx.AsyncClient(
        base_url=HL_BASE,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post("conversations/messages", json=payload)
        r.raise_for_status()
        data = r.json()

    message_id = data.get("messageId") or data.get("id")
    log.info("highlevel.send_sms", contact_id=contact_id, message_id=message_id)
    return {
        "message_id": message_id,
        "contact_id": contact_id,
        "from_number": from_number,
        "status": data.get("status", "sent"),
        "raw": data,
    }
