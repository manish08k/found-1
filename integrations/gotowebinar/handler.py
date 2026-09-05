"""GoToWebinar integration — webinars, registrants, sessions."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

GTW_BASE = "https://api.getgo.com/G2W/rest/v2/"


async def _gtw_client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token")
    organizer_key = creds.get("organizer_key") or creds.get("organizerKey", "")
    return httpx.AsyncClient(
        base_url=GTW_BASE,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    ), organizer_key


@register_node("gotowebinar.list_webinars")
async def gtw_list_webinars(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all webinars for the authenticated organizer.

    config:
      from_time   — ISO-8601 start date filter (e.g. 2024-01-01T00:00:00Z)
      to_time     — ISO-8601 end date filter
      page        — page number (default 0)
      page_size   — results per page (default 100, max 200)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token")
    organizer_key = creds.get("organizer_key") or creds.get("organizerKey", "")

    from_time = config.get("from_time") or input_data.get("from_time", "2000-01-01T00:00:00Z")
    to_time = config.get("to_time") or input_data.get("to_time", "2099-12-31T23:59:59Z")
    page = int(config.get("page", 0))
    page_size = int(config.get("page_size", 100))

    params = {
        "fromTime": from_time,
        "toTime": to_time,
        "page": page,
        "size": page_size,
    }

    async with httpx.AsyncClient(
        base_url=GTW_BASE,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get(
            f"organizers/{organizer_key}/webinars",
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    webinars = data.get("_embedded", {}).get("webinars", data if isinstance(data, list) else [])
    log.info("gotowebinar.list_webinars", count=len(webinars), organizer_key=organizer_key)
    return {
        "webinars": webinars,
        "count": len(webinars),
        "page": page,
        "total": data.get("total", len(webinars)),
    }


@register_node("gotowebinar.create_webinar")
async def gtw_create_webinar(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new webinar.

    config/input_data:
      subject     — webinar title (required)
      description — webinar description
      times       — list of {startTime, endTime} dicts (ISO-8601)
      timezone    — IANA timezone (default America/New_York)
      type        — single_session | series | sequence (default single_session)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token")
    organizer_key = creds.get("organizer_key") or creds.get("organizerKey", "")

    subject = config.get("subject") or input_data.get("subject", "New Webinar")
    description = config.get("description") or input_data.get("description", "")
    times = config.get("times") or input_data.get("times", [])
    timezone = config.get("timezone") or input_data.get("timezone", "America/New_York")
    webinar_type = config.get("type") or input_data.get("type", "single_session")

    payload = {
        "subject": subject,
        "description": description,
        "times": times,
        "timeZone": timezone,
        "type": webinar_type,
    }

    async with httpx.AsyncClient(
        base_url=GTW_BASE,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post(
            f"organizers/{organizer_key}/webinars",
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    webinar_key = data.get("webinarKey") or data.get("webinarID")
    log.info("gotowebinar.create_webinar", webinar_key=webinar_key, subject=subject)
    return {
        "webinar_key": webinar_key,
        "subject": subject,
        "times": times,
        "raw": data,
    }


@register_node("gotowebinar.list_registrants")
async def gtw_list_registrants(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List registrants for a specific webinar.

    config/input_data:
      webinar_key — GoToWebinar webinar key (required)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token")
    organizer_key = creds.get("organizer_key") or creds.get("organizerKey", "")
    webinar_key = config.get("webinar_key") or input_data.get("webinar_key")

    if not webinar_key:
        raise ValueError("webinar_key is required for gotowebinar.list_registrants")

    async with httpx.AsyncClient(
        base_url=GTW_BASE,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.get(
            f"organizers/{organizer_key}/webinars/{webinar_key}/registrants",
        )
        r.raise_for_status()
        data = r.json()

    registrants = data if isinstance(data, list) else data.get("registrants", [])
    log.info("gotowebinar.list_registrants", webinar_key=webinar_key, count=len(registrants))
    return {
        "registrants": registrants,
        "count": len(registrants),
        "webinar_key": webinar_key,
    }


@register_node("gotowebinar.register_attendee")
async def gtw_register_attendee(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Register an attendee for a webinar.

    config/input_data:
      webinar_key  — GoToWebinar webinar key (required)
      first_name   — attendee first name (required)
      last_name    — attendee last name (required)
      email        — attendee email address (required)
      source       — optional registration source tag
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token")
    organizer_key = creds.get("organizer_key") or creds.get("organizerKey", "")
    webinar_key = config.get("webinar_key") or input_data.get("webinar_key")

    if not webinar_key:
        raise ValueError("webinar_key is required for gotowebinar.register_attendee")

    payload = {
        "firstName": config.get("first_name") or input_data.get("first_name", ""),
        "lastName": config.get("last_name") or input_data.get("last_name", ""),
        "email": config.get("email") or input_data.get("email", ""),
    }
    source = config.get("source") or input_data.get("source")
    if source:
        payload["source"] = source

    async with httpx.AsyncClient(
        base_url=GTW_BASE,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    ) as client:
        r = await client.post(
            f"organizers/{organizer_key}/webinars/{webinar_key}/registrants",
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    registrant_key = data.get("registrantKey")
    join_url = data.get("joinUrl")
    log.info("gotowebinar.register_attendee", webinar_key=webinar_key, registrant_key=registrant_key)
    return {
        "registrant_key": registrant_key,
        "join_url": join_url,
        "email": payload["email"],
        "webinar_key": webinar_key,
        "raw": data,
    }
