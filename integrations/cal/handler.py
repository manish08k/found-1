"""
Cal.com scheduling platform integration.

Provides booking management, event type listing, and booking cancellation
via the Cal.com REST API v1.

Credential fields:
  - api_key : Cal.com API key (from Settings > Developer > API Keys).

Auth: api_key passed as a query parameter on every request.
Base URL: https://api.cal.com/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.cal.com/v1"


async def _get_api_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Cal.com credential missing 'api_key'")
    return api_key


def _make_client(api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE_URL,
        params={"apiKey": api_key},
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cal.com API error {r.status_code}: {detail}")


@register_node("cal.list_bookings")
async def cal_list_bookings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List bookings for the authenticated user.

    Params:
      - status: Filter by booking status — 'upcoming', 'recurring', 'past',
                'cancelled', 'unconfirmed'. Omit for all.
      - take: Number of bookings to return (default 10, max 100).
      - skip: Number of bookings to skip (default 0).
      - event_type_id: Filter to a specific event type.
      - date_from: ISO-8601 date string — return bookings after this date.
      - date_to: ISO-8601 date string — return bookings before this date.
    """
    api_key = await _get_api_key(credential_id, db)
    status = config.get("status") or input_data.get("status")
    take = min(int(config.get("take") or input_data.get("take", 10)), 100)
    skip = int(config.get("skip") or input_data.get("skip", 0))
    event_type_id = config.get("event_type_id") or input_data.get("event_type_id")
    date_from = config.get("date_from") or input_data.get("date_from")
    date_to = config.get("date_to") or input_data.get("date_to")

    params: dict = {"take": take, "skip": skip}
    if status:
        params["status"] = status
    if event_type_id:
        params["eventTypeId"] = event_type_id
    if date_from:
        params["dateFrom"] = date_from
    if date_to:
        params["dateTo"] = date_to

    async with _make_client(api_key) as client:
        r = await client.get("/bookings", params=params)
        _raise_for_status(r)
        data = r.json()

    bookings = data.get("bookings", data) if isinstance(data, dict) else data
    log.info("cal.list_bookings", count=len(bookings) if isinstance(bookings, list) else 0)
    return {"bookings": bookings, "count": len(bookings) if isinstance(bookings, list) else 0}


@register_node("cal.create_booking")
async def cal_create_booking(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a new booking on Cal.com.

    Params:
      - event_type_id (required): The ID of the event type to book.
      - start (required): ISO-8601 datetime string for the booking start.
      - end (required): ISO-8601 datetime string for the booking end.
      - name (required): Attendee name.
      - email (required): Attendee email.
      - timezone (required): IANA timezone string (e.g. 'America/New_York').
      - title: Custom booking title (overrides event type title).
      - description: Notes or description for the booking.
      - metadata: Dict of additional metadata to attach.
      - language: Attendee language (default 'en').
      - location: Location override.
      - custom_inputs: List of custom input dicts for the event type form.
      - guests: Comma-separated list of additional attendee emails.
    """
    api_key = await _get_api_key(credential_id, db)
    event_type_id = config.get("event_type_id") or input_data.get("event_type_id")
    start = config.get("start") or input_data.get("start")
    end = config.get("end") or input_data.get("end")
    name = config.get("name") or input_data.get("name")
    email = config.get("email") or input_data.get("email")
    timezone = config.get("timezone") or input_data.get("timezone")

    for field, val in [("event_type_id", event_type_id), ("start", start), ("end", end),
                       ("name", name), ("email", email), ("timezone", timezone)]:
        if not val:
            raise ValueError(f"cal.create_booking requires '{field}'")

    payload: dict = {
        "eventTypeId": int(event_type_id),
        "start": start,
        "end": end,
        "responses": {
            "name": name,
            "email": email,
            "location": config.get("location") or input_data.get("location", {"optionValue": "", "value": "inPerson"}),
        },
        "timeZone": timezone,
        "language": config.get("language") or input_data.get("language", "en"),
        "metadata": config.get("metadata") or input_data.get("metadata", {}),
    }

    title = config.get("title") or input_data.get("title")
    if title:
        payload["title"] = title

    description = config.get("description") or input_data.get("description")
    if description:
        payload["description"] = description

    custom_inputs = config.get("custom_inputs") or input_data.get("custom_inputs", [])
    if isinstance(custom_inputs, str):
        import json
        custom_inputs = json.loads(custom_inputs)
    if custom_inputs:
        payload["customInputs"] = custom_inputs

    guests_raw = config.get("guests") or input_data.get("guests")
    if guests_raw:
        payload["guests"] = [g.strip() for g in str(guests_raw).split(",") if g.strip()]

    async with _make_client(api_key) as client:
        r = await client.post("/bookings", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("cal.create_booking", id=data.get("id"), uid=data.get("uid"))
    return {"booking": data, "id": data.get("id"), "uid": data.get("uid")}


@register_node("cal.cancel_booking")
async def cal_cancel_booking(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Cancel an existing booking.

    Params:
      - booking_id (required): The numeric ID of the booking to cancel.
      - reason: Optional cancellation reason message.
      - all_remaining: bool — for recurring bookings, cancel all future occurrences.
    """
    api_key = await _get_api_key(credential_id, db)
    booking_id = config.get("booking_id") or input_data.get("booking_id")
    if not booking_id:
        raise ValueError("cal.cancel_booking requires 'booking_id'")

    payload: dict = {}
    reason = config.get("reason") or input_data.get("reason")
    if reason:
        payload["reason"] = reason

    all_remaining = config.get("all_remaining") or input_data.get("all_remaining", False)
    if all_remaining:
        payload["allRemainingBookings"] = True

    async with _make_client(api_key) as client:
        r = await client.delete(f"/bookings/{booking_id}", json=payload if payload else None)
        _raise_for_status(r)
        data = {}
        if r.content:
            try:
                data = r.json()
            except Exception:
                pass

    log.info("cal.cancel_booking", booking_id=booking_id)
    return {"cancelled": True, "booking_id": booking_id, "response": data}


@register_node("cal.list_event_types")
async def cal_list_event_types(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List event types for the authenticated user or a specific profile.

    Params:
      - profile_username: Filter to a specific Cal.com username.
      - event_slug: Filter to a specific event type slug.
    """
    api_key = await _get_api_key(credential_id, db)
    profile_username = config.get("profile_username") or input_data.get("profile_username")
    event_slug = config.get("event_slug") or input_data.get("event_slug")

    params: dict = {}
    if profile_username:
        params["profileUsername"] = profile_username
    if event_slug:
        params["eventSlug"] = event_slug

    async with _make_client(api_key) as client:
        r = await client.get("/event-types", params=params)
        _raise_for_status(r)
        data = r.json()

    event_types = data.get("event_types", data) if isinstance(data, dict) else data
    log.info("cal.list_event_types", count=len(event_types) if isinstance(event_types, list) else 0)
    return {
        "event_types": event_types,
        "count": len(event_types) if isinstance(event_types, list) else 0,
    }


@register_node("cal.get_booking")
async def cal_get_booking(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve a single booking by ID or UID.

    Params:
      - booking_id (required): The numeric ID or UID string of the booking.
    """
    api_key = await _get_api_key(credential_id, db)
    booking_id = config.get("booking_id") or input_data.get("booking_id")
    if not booking_id:
        raise ValueError("cal.get_booking requires 'booking_id'")

    async with _make_client(api_key) as client:
        r = await client.get(f"/bookings/{booking_id}")
        _raise_for_status(r)
        data = r.json()

    booking = data.get("booking", data) if isinstance(data, dict) and "booking" in data else data
    return {"booking": booking}
