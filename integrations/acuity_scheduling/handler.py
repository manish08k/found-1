"""
Acuity Scheduling appointment booking integration.

Provides appointment management, cancellation, and appointment-type
listing via the Acuity Scheduling API v1.

Credential fields:
  - user_id : Acuity Scheduling user ID
  - api_key  : Acuity API key

Auth: HTTP Basic (user_id : api_key).
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://acuityscheduling.com/api/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    user_id = creds.get("user_id")
    api_key = creds.get("api_key")
    if not user_id:
        raise ValueError("Acuity Scheduling credential missing 'user_id'")
    if not api_key:
        raise ValueError("Acuity Scheduling credential missing 'api_key'")

    token = base64.b64encode(f"{user_id}:{api_key}".encode()).decode()
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Basic {token}",
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
        raise ValueError(f"Acuity Scheduling API error {r.status_code}: {detail}")


@register_node("acuity.list_appointments")
async def ac_list_appointments(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List upcoming or filtered appointments."""
    max_count = int(config.get("max") or input_data.get("max", 50))
    min_date = config.get("minDate") or input_data.get("minDate")
    max_date = config.get("maxDate") or input_data.get("maxDate")
    appointment_type_id = config.get("appointmentTypeID") or input_data.get("appointmentTypeID")
    calendar_id = config.get("calendarID") or input_data.get("calendarID")

    params: dict = {"max": max_count}
    if min_date:
        params["minDate"] = min_date
    if max_date:
        params["maxDate"] = max_date
    if appointment_type_id:
        params["appointmentTypeID"] = appointment_type_id
    if calendar_id:
        params["calendarID"] = calendar_id

    async with await _client(credential_id, db) as client:
        r = await client.get("/appointments", params=params)
        _raise_for_status(r)
        appointments = r.json()

    return {"appointments": appointments, "count": len(appointments)}


@register_node("acuity.create_appointment")
async def ac_create_appointment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Book a new appointment."""
    appointment_type_id = config.get("appointmentTypeID") or input_data.get("appointmentTypeID")
    datetime_val = config.get("datetime") or input_data.get("datetime")
    first_name = config.get("firstName") or input_data.get("firstName", "")
    last_name = config.get("lastName") or input_data.get("lastName", "")
    email = config.get("email") or input_data.get("email")

    if not appointment_type_id:
        raise ValueError("acuity.create_appointment requires 'appointmentTypeID'")
    if not datetime_val:
        raise ValueError("acuity.create_appointment requires 'datetime' (ISO 8601 string)")
    if not email:
        raise ValueError("acuity.create_appointment requires 'email'")

    payload: dict = {
        "appointmentTypeID": int(appointment_type_id),
        "datetime": datetime_val,
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
    }

    # Optional fields
    for field in ("phone", "notes", "calendarID", "timezone"):
        val = config.get(field) or input_data.get(field)
        if val is not None:
            payload[field] = val

    # Custom fields passed as a list
    fields = config.get("fields") or input_data.get("fields")
    if fields:
        payload["fields"] = fields

    async with await _client(credential_id, db) as client:
        r = await client.post("/appointments", json=payload)
        _raise_for_status(r)
        appointment = r.json()

    log.info("acuity.create_appointment", appointment_id=appointment.get("id"), email=email)
    return {"appointment": appointment, "appointment_id": appointment.get("id")}


@register_node("acuity.cancel_appointment")
async def ac_cancel_appointment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Cancel an existing appointment by its ID."""
    appointment_id = config.get("appointment_id") or input_data.get("appointment_id")
    if not appointment_id:
        raise ValueError("acuity.cancel_appointment requires 'appointment_id'")

    notify_client = config.get("noEmail") or input_data.get("noEmail", False)
    payload = {"noEmail": bool(notify_client)}

    async with await _client(credential_id, db) as client:
        r = await client.put(f"/appointments/{appointment_id}/cancel", json=payload)
        _raise_for_status(r)
        result = r.json()

    log.info("acuity.cancel_appointment", appointment_id=appointment_id)
    return {"appointment": result, "cancelled": True}


@register_node("acuity.list_appointment_types")
async def ac_list_appointment_types(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all appointment types configured in Acuity."""
    category = config.get("category") or input_data.get("category")
    params = {}
    if category:
        params["category"] = category

    async with await _client(credential_id, db) as client:
        r = await client.get("/appointment-types", params=params)
        _raise_for_status(r)
        types = r.json()

    return {"appointment_types": types, "count": len(types)}


@register_node("acuity.get_appointment")
async def ac_get_appointment(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve details of a single appointment by ID."""
    appointment_id = config.get("appointment_id") or input_data.get("appointment_id")
    if not appointment_id:
        raise ValueError("acuity.get_appointment requires 'appointment_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/appointments/{appointment_id}")
        _raise_for_status(r)
        appointment = r.json()

    return {"appointment": appointment}
