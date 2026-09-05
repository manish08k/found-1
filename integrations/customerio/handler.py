"""
Customer.io messaging integration.

Provides customer identification, event tracking, transactional email sending,
and customer deletion via the Customer.io REST and Tracking APIs.

Credential fields (one of two auth schemes):
  Scheme A – Basic auth for Tracking API:
    - site_id  : Customer.io Site ID
    - api_key  : Customer.io API key (used as password in Basic auth)
  Scheme B – Bearer auth for App API:
    - api_key  : Customer.io App API key

Auth:
  - Tracking endpoints: HTTP Basic auth  (site_id : api_key)
  - App endpoints     : Bearer <api_key>

Base URLs:
  - App API      : https://api.customer.io/v1/
  - Tracking API : https://track.customer.io/api/v1/
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_APP_BASE = "https://api.customer.io/v1"
_TRACK_BASE = "https://track.customer.io/api/v1"


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Customer.io API error {r.status_code}: {detail}")


async def _app_client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Customer.io credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_APP_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


async def _track_client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    site_id = creds.get("site_id", "")
    api_key = creds.get("api_key", "")
    if not site_id or not api_key:
        raise ValueError("Customer.io credential missing 'site_id' or 'api_key'")
    token = base64.b64encode(f"{site_id}:{api_key}".encode()).decode()
    return httpx.AsyncClient(
        base_url=_TRACK_BASE,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


@register_node("customerio.identify")
async def cio_identify(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create or update a customer profile in Customer.io."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    email = config.get("email") or input_data.get("email")
    attributes = config.get("attributes") or input_data.get("attributes", {})

    if not customer_id:
        raise ValueError("customerio.identify requires 'customer_id'")

    payload: dict = {}
    if email:
        payload["email"] = email
    if isinstance(attributes, dict):
        payload.update(attributes)

    async with await _track_client(credential_id, db) as client:
        r = await client.put(f"/customers/{customer_id}", json=payload)
        _raise_for_status(r)

    log.info("customerio.identify: customer identified", customer_id=customer_id)
    return {"identified": True, "customer_id": customer_id}


@register_node("customerio.track_event")
async def cio_track_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Track a named event for a customer."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    event_name = config.get("event_name") or input_data.get("event_name")
    event_data = config.get("data") or input_data.get("data", {})

    if not customer_id:
        raise ValueError("customerio.track_event requires 'customer_id'")
    if not event_name:
        raise ValueError("customerio.track_event requires 'event_name'")

    payload: dict = {"name": event_name}
    if isinstance(event_data, dict) and event_data:
        payload["data"] = event_data

    async with await _track_client(credential_id, db) as client:
        r = await client.post(f"/customers/{customer_id}/events", json=payload)
        _raise_for_status(r)

    log.info("customerio.track_event: event tracked", customer_id=customer_id, event=event_name)
    return {"tracked": True, "customer_id": customer_id, "event_name": event_name}


@register_node("customerio.send_email")
async def cio_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a transactional email via Customer.io App API."""
    to = config.get("to") or input_data.get("to")
    transactional_message_id = (
        config.get("transactional_message_id") or input_data.get("transactional_message_id")
    )
    identifiers = config.get("identifiers") or input_data.get("identifiers", {})
    message_data = config.get("message_data") or input_data.get("message_data", {})

    if not to:
        raise ValueError("customerio.send_email requires 'to'")
    if not transactional_message_id:
        raise ValueError("customerio.send_email requires 'transactional_message_id'")

    payload: dict = {
        "to": to,
        "transactional_message_id": transactional_message_id,
    }
    if identifiers:
        payload["identifiers"] = identifiers
    if message_data:
        payload["message_data"] = message_data

    async with await _app_client(credential_id, db) as client:
        r = await client.post("/send/email", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("customerio.send_email: email sent", to=to)
    return {"sent": True, "delivery_id": data.get("delivery_id"), "queued_at": data.get("queued_at")}


@register_node("customerio.delete_customer")
async def cio_delete_customer(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Delete a customer from Customer.io."""
    customer_id = config.get("customer_id") or input_data.get("customer_id")
    if not customer_id:
        raise ValueError("customerio.delete_customer requires 'customer_id'")

    async with await _track_client(credential_id, db) as client:
        r = await client.delete(f"/customers/{customer_id}")
        _raise_for_status(r)

    log.info("customerio.delete_customer: customer deleted", customer_id=customer_id)
    return {"deleted": True, "customer_id": customer_id}
