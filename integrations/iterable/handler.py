"""
Iterable marketing platform integration.

Provides user management, event tracking, email sending, and campaign
listing via the Iterable API.

Credential fields:
  - api_key : Iterable API key (sent as 'Api-Key' header)

Base URL: https://api.iterable.com/api/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.iterable.com/api"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("iterable credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"Api-Key": api_key, "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Iterable API error {r.status_code}: {detail}")


@register_node("iterable.create_user")
async def iterable_create_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create or update a user in Iterable.

    Config / input_data fields:
      - email       (required) : user email address
      - data_fields            : dict of additional profile fields (optional)
      - user_id                : optional Iterable user ID
      - prefer_user_id         : bool, prefer userId over email (default False)
    """
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("iterable.create_user requires 'email'")

    data_fields = config.get("data_fields") or input_data.get("data_fields", {})
    user_id = config.get("user_id") or input_data.get("user_id")
    prefer_user_id = bool(config.get("prefer_user_id") or input_data.get("prefer_user_id", False))

    payload: dict = {"email": email}
    if data_fields:
        payload["dataFields"] = data_fields
    if user_id:
        payload["userId"] = str(user_id)
    if prefer_user_id:
        payload["preferUserId"] = prefer_user_id

    log.info("iterable.create_user", email=email)
    async with await _client(credential_id, db) as client:
        r = await client.post("/users/update", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"success": True, "email": email, "response": data}


@register_node("iterable.track_event")
async def iterable_track_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Track a custom event for a user.

    Config / input_data fields:
      - email      (required) : user email address
      - event_name (required) : name of the event to track
      - data_fields           : dict of event properties (optional)
      - campaign_id           : associated campaign ID (optional)
      - template_id           : associated template ID (optional)
    """
    email = config.get("email") or input_data.get("email")
    event_name = config.get("event_name") or input_data.get("event_name")

    if not email:
        raise ValueError("iterable.track_event requires 'email'")
    if not event_name:
        raise ValueError("iterable.track_event requires 'event_name'")

    data_fields = config.get("data_fields") or input_data.get("data_fields", {})
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    template_id = config.get("template_id") or input_data.get("template_id")

    payload: dict = {"email": email, "eventName": event_name}
    if data_fields:
        payload["dataFields"] = data_fields
    if campaign_id:
        payload["campaignId"] = int(campaign_id)
    if template_id:
        payload["templateId"] = int(template_id)

    log.info("iterable.track_event", email=email, event_name=event_name)
    async with await _client(credential_id, db) as client:
        r = await client.post("/events/track", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"success": True, "email": email, "event_name": event_name, "response": data}


@register_node("iterable.send_email")
async def iterable_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a transactional email via Iterable.

    Config / input_data fields:
      - campaign_id  (required) : Iterable campaign ID
      - recipient_email (required) : recipient email address
      - data_fields               : dict of template variables (optional)
      - send_at                   : scheduled send time (ISO 8601, optional)
    """
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    recipient_email = config.get("recipient_email") or input_data.get("recipient_email")

    if not campaign_id:
        raise ValueError("iterable.send_email requires 'campaign_id'")
    if not recipient_email:
        raise ValueError("iterable.send_email requires 'recipient_email'")

    data_fields = config.get("data_fields") or input_data.get("data_fields", {})
    send_at = config.get("send_at") or input_data.get("send_at")

    payload: dict = {
        "campaignId": int(campaign_id),
        "recipientEmail": recipient_email,
    }
    if data_fields:
        payload["dataFields"] = data_fields
    if send_at:
        payload["sendAt"] = send_at

    log.info("iterable.send_email", campaign_id=campaign_id, recipient=recipient_email)
    async with await _client(credential_id, db) as client:
        r = await client.post("/email/target", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"success": True, "campaign_id": campaign_id, "recipient": recipient_email, "response": data}


@register_node("iterable.list_campaigns")
async def iterable_list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all campaigns in the Iterable project.

    Config / input_data fields: none required.

    Returns:
      { "campaigns": [...], "count": int }
    """
    log.info("iterable.list_campaigns")
    async with await _client(credential_id, db) as client:
        r = await client.get("/campaigns")
        _raise_for_status(r)
        data = r.json()

    campaigns = data.get("campaigns", data if isinstance(data, list) else [])
    return {"campaigns": campaigns, "count": len(campaigns)}
