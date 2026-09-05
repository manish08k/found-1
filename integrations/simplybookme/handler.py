"""SimplyBookMe — appointment scheduling integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SIMPLYBOOK_BASE = "https://user-api.simplybook.me/admin"


async def _get_token(config: dict) -> str:
    """Authenticate with SimplyBookMe and return a session token."""
    company = config.get("company", "")
    login = config.get("login", "")
    password = config.get("password", "")

    async with httpx.AsyncClient(base_url=SIMPLYBOOK_BASE, timeout=30) as client:
        r = await client.post(
            "/login",
            json={"company": company, "login": login, "password": password},
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    token = data.get("token") or data.get("result")
    if not token:
        raise ValueError("SimplyBookMe authentication failed: no token returned")
    return token


@register_node("simplybookme.list_bookings")
async def simplybookme_list_bookings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List bookings from SimplyBookMe.

    config:
      company  — SimplyBookMe company login
      login    — user login
      password — user password
    """
    token = await _get_token(config)

    async with httpx.AsyncClient(base_url=SIMPLYBOOK_BASE, timeout=30) as client:
        r = await client.post(
            "/getBookings",
            json={"filter": {}},
            headers={"Content-Type": "application/json", "X-Company-Login": config.get("company", ""), "X-Token": token},
        )
        r.raise_for_status()
        data = r.json()

    bookings = data.get("result", data if isinstance(data, list) else [])
    log.info("simplybookme.list_bookings", count=len(bookings))
    return {"bookings": bookings, "count": len(bookings)}


@register_node("simplybookme.list_services")
async def simplybookme_list_services(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List services from SimplyBookMe.

    config:
      company  — SimplyBookMe company login
      login    — user login
      password — user password
    """
    token = await _get_token(config)

    async with httpx.AsyncClient(base_url=SIMPLYBOOK_BASE, timeout=30) as client:
        r = await client.post(
            "/getServiceList",
            json={},
            headers={"Content-Type": "application/json", "X-Company-Login": config.get("company", ""), "X-Token": token},
        )
        r.raise_for_status()
        data = r.json()

    services = data.get("result", data if isinstance(data, list) else [])
    log.info("simplybookme.list_services", count=len(services))
    return {"services": services, "count": len(services)}


@register_node("simplybookme.create_booking")
async def simplybookme_create_booking(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a booking in SimplyBookMe.

    config/input_data:
      company      — SimplyBookMe company login
      login        — user login
      password     — user password
      service_id   — service ID (required)
      performer_id — provider/performer ID (required)
      date         — booking date in YYYY-MM-DD format (required)
      time         — booking time in HH:MM format (required)
      client_name  — client full name (required)
      client_email — client email address (required)
    """
    service_id = config.get("service_id") or input_data.get("service_id")
    performer_id = config.get("performer_id") or input_data.get("performer_id")
    date = config.get("date") or input_data.get("date")
    time = config.get("time") or input_data.get("time")
    client_name = config.get("client_name") or input_data.get("client_name")
    client_email = config.get("client_email") or input_data.get("client_email")

    if not service_id:
        raise ValueError("service_id is required for simplybookme.create_booking")
    if not performer_id:
        raise ValueError("performer_id is required for simplybookme.create_booking")
    if not date:
        raise ValueError("date is required for simplybookme.create_booking")
    if not time:
        raise ValueError("time is required for simplybookme.create_booking")
    if not client_name:
        raise ValueError("client_name is required for simplybookme.create_booking")
    if not client_email:
        raise ValueError("client_email is required for simplybookme.create_booking")

    token = await _get_token(config)

    payload = {
        "service_id": service_id,
        "performer_id": performer_id,
        "date": date,
        "time": time,
        "client": {"name": client_name, "email": client_email},
    }

    async with httpx.AsyncClient(base_url=SIMPLYBOOK_BASE, timeout=30) as client:
        r = await client.post(
            "/book",
            json=payload,
            headers={"Content-Type": "application/json", "X-Company-Login": config.get("company", ""), "X-Token": token},
        )
        r.raise_for_status()
        data = r.json()

    booking = data.get("result", data)
    log.info("simplybookme.create_booking", service_id=service_id, date=date, client_email=client_email)
    return {"booking": booking, "service_id": service_id, "date": date, "time": time}
