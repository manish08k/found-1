"""
Eventbrite integration.

Credential fields:
  - api_key: Private OAuth token (Authorization: Bearer header)

Auth: Authorization: Bearer {api_key}
Base URL: https://www.eventbriteapi.com/v3
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://www.eventbriteapi.com/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key") or creds.get("private_token")
    if not api_key:
        raise ValueError("Eventbrite credential is missing 'api_key' or 'private_token'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Eventbrite API error {r.status_code}: {detail}")
    return r.json()


async def test_connection(credential_id: str, db) -> dict:
    """Verify credentials by fetching the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me/")
    return _check(r)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

@register_node("eventbrite.list_organizations")
async def eventbrite_list_organizations(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/me/organizations/ — list organizations for the current user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me/organizations/")
    return _check(r)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@register_node("eventbrite.list_events")
async def eventbrite_list_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /organizations/{org_id}/events/ — list events for an organization."""
    org_id = config.get("org_id") or input_data.get("org_id")
    if not org_id:
        raise ValueError("eventbrite.list_events requires 'org_id'")
    params: dict = {}
    status = config.get("status") or input_data.get("status")
    if status:
        params["status"] = status
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/organizations/{org_id}/events/", params=params)
    return _check(r)


@register_node("eventbrite.get_event")
async def eventbrite_get_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /events/{event_id}/ — get event details."""
    event_id = config.get("event_id") or input_data.get("event_id")
    if not event_id:
        raise ValueError("eventbrite.get_event requires 'event_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/events/{event_id}/")
    return _check(r)


@register_node("eventbrite.create_event")
async def eventbrite_create_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /organizations/{org_id}/events/ — create a new event."""
    org_id = config.get("org_id") or input_data.get("org_id")
    name = config.get("name") or input_data.get("name")
    start_utc = config.get("start_utc") or input_data.get("start_utc")
    end_utc = config.get("end_utc") or input_data.get("end_utc")
    currency = config.get("currency") or input_data.get("currency", "USD")
    if not org_id or not name or not start_utc or not end_utc:
        raise ValueError("eventbrite.create_event requires 'org_id', 'name', 'start_utc', 'end_utc'")
    body: dict = {
        "event": {
            "name": {"html": name},
            "start": {"timezone": "UTC", "utc": start_utc},
            "end": {"timezone": "UTC", "utc": end_utc},
            "currency": currency,
        }
    }
    description = config.get("description") or input_data.get("description")
    if description:
        body["event"]["description"] = {"html": description}
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/organizations/{org_id}/events/", json=body)
    return _check(r)


@register_node("eventbrite.publish_event")
async def eventbrite_publish_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /events/{event_id}/publish/ — publish an event."""
    event_id = config.get("event_id") or input_data.get("event_id")
    if not event_id:
        raise ValueError("eventbrite.publish_event requires 'event_id'")
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/events/{event_id}/publish/")
    return _check(r)


# ---------------------------------------------------------------------------
# Orders & Attendees
# ---------------------------------------------------------------------------

@register_node("eventbrite.list_orders")
async def eventbrite_list_orders(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /events/{event_id}/orders/ — list orders for an event."""
    event_id = config.get("event_id") or input_data.get("event_id")
    if not event_id:
        raise ValueError("eventbrite.list_orders requires 'event_id'")
    params: dict = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/events/{event_id}/orders/", params=params)
    return _check(r)


@register_node("eventbrite.get_order")
async def eventbrite_get_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /orders/{order_id}/ — get order details."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("eventbrite.get_order requires 'order_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/orders/{order_id}/")
    return _check(r)


@register_node("eventbrite.list_attendees")
async def eventbrite_list_attendees(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /events/{event_id}/attendees/ — list attendees for an event."""
    event_id = config.get("event_id") or input_data.get("event_id")
    if not event_id:
        raise ValueError("eventbrite.list_attendees requires 'event_id'")
    params: dict = {}
    page = config.get("page") or input_data.get("page")
    if page:
        params["page"] = int(page)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/events/{event_id}/attendees/", params=params)
    return _check(r)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@register_node("eventbrite.list_categories")
async def eventbrite_list_categories(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /categories/ — list event categories."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/categories/")
    return _check(r)


# ---------------------------------------------------------------------------
# Venues
# ---------------------------------------------------------------------------

@register_node("eventbrite.list_venues")
async def eventbrite_list_venues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /organizations/{org_id}/venues/ — list venues for an organization."""
    org_id = config.get("org_id") or input_data.get("org_id")
    if not org_id:
        raise ValueError("eventbrite.list_venues requires 'org_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/organizations/{org_id}/venues/")
    return _check(r)


@register_node("eventbrite.create_venue")
async def eventbrite_create_venue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /organizations/{org_id}/venues/ — create a venue."""
    org_id = config.get("org_id") or input_data.get("org_id")
    name = config.get("name") or input_data.get("name")
    if not org_id or not name:
        raise ValueError("eventbrite.create_venue requires 'org_id' and 'name'")
    body: dict = {"venue": {"name": name}}
    address = config.get("address") or input_data.get("address")
    if address:
        body["venue"]["address"] = address
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/organizations/{org_id}/venues/", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

@register_node("eventbrite.get_current_user")
async def eventbrite_get_current_user(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /users/me/ — get the current authenticated user."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/users/me/")
    return _check(r)
