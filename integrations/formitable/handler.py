"""Formitable integration — restaurant reservation management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FORMITABLE_BASE = "https://api.formitable.com/v1"


def _formitable_headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


@register_node("formitable.list_reservations")
async def formitable_list_reservations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List reservations from Formitable.

    config:
      api_key    — Formitable API key (required)
      date_from  — start date filter (optional, e.g. "2024-01-01")
      date_to    — end date filter (optional, e.g. "2024-12-31")
      status     — reservation status filter (optional)
      limit      — max records to return (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params = {}
    if merged.get("date_from"):
        params["date_from"] = merged["date_from"]
    if merged.get("date_to"):
        params["date_to"] = merged["date_to"]
    if merged.get("status"):
        params["status"] = merged["status"]
    if merged.get("limit") is not None:
        params["limit"] = merged["limit"]

    async with httpx.AsyncClient(base_url=FORMITABLE_BASE, timeout=30) as client:
        r = await client.get(
            "/reservations",
            headers=_formitable_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    reservations = data.get("reservations", data) if isinstance(data, dict) else data
    log.info("formitable.list_reservations", count=len(reservations))
    return {"reservations": reservations, "count": len(reservations)}


@register_node("formitable.get_reservation")
async def formitable_get_reservation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Formitable reservation.

    config:
      api_key        — Formitable API key (required)
      reservation_id — reservation ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    reservation_id = merged.get("reservation_id")
    if not reservation_id:
        raise ValueError("reservation_id is required for formitable.get_reservation")

    async with httpx.AsyncClient(base_url=FORMITABLE_BASE, timeout=30) as client:
        r = await client.get(
            f"/reservations/{reservation_id}",
            headers=_formitable_headers(api_key),
        )
        r.raise_for_status()
        reservation = r.json()

    log.info("formitable.get_reservation", reservation_id=reservation_id)
    return {"reservation": reservation, "reservation_id": reservation_id}


@register_node("formitable.create_reservation")
async def formitable_create_reservation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new reservation in Formitable.

    config:
      api_key    — Formitable API key (required)
      date       — reservation date (required, e.g. "2024-06-15")
      time       — reservation time (required, e.g. "19:00")
      covers     — number of guests (required)
      first_name — guest first name (required)
      last_name  — guest last name (required)
      email      — guest email (optional)
      phone      — guest phone (optional)
      notes      — reservation notes (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    for field in ("date", "time", "covers", "first_name", "last_name"):
        if not merged.get(field):
            raise ValueError(f"{field} is required for formitable.create_reservation")

    payload = {
        "date": merged["date"],
        "time": merged["time"],
        "covers": merged["covers"],
        "first_name": merged["first_name"],
        "last_name": merged["last_name"],
    }
    if merged.get("email"):
        payload["email"] = merged["email"]
    if merged.get("phone"):
        payload["phone"] = merged["phone"]
    if merged.get("notes"):
        payload["notes"] = merged["notes"]

    async with httpx.AsyncClient(base_url=FORMITABLE_BASE, timeout=30) as client:
        r = await client.post(
            "/reservations",
            headers=_formitable_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        reservation = r.json()

    reservation_id = reservation.get("id") if isinstance(reservation, dict) else None
    log.info("formitable.create_reservation", reservation_id=reservation_id)
    return {"reservation": reservation, "reservation_id": reservation_id}


@register_node("formitable.update_reservation")
async def formitable_update_reservation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing Formitable reservation.

    config:
      api_key        — Formitable API key (required)
      reservation_id — reservation ID to update (required)
      date           — new date (optional)
      time           — new time (optional)
      covers         — new guest count (optional)
      status         — new status (optional)
      notes          — updated notes (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    reservation_id = merged.get("reservation_id")
    if not reservation_id:
        raise ValueError("reservation_id is required for formitable.update_reservation")

    payload = {}
    for field in ("date", "time", "covers", "status", "notes", "first_name", "last_name", "email", "phone"):
        if merged.get(field) is not None:
            payload[field] = merged[field]

    async with httpx.AsyncClient(base_url=FORMITABLE_BASE, timeout=30) as client:
        r = await client.patch(
            f"/reservations/{reservation_id}",
            headers=_formitable_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        reservation = r.json()

    log.info("formitable.update_reservation", reservation_id=reservation_id)
    return {"reservation": reservation, "reservation_id": reservation_id}
