"""Close CRM integration — leads, activities, and notes."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CLOSE_BASE = "https://api.close.com/api/v1"


@register_node("close.list_leads")
async def close_list_leads(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List leads from Close CRM.

    config/input_data:
      api_key — Close API key (required, used as HTTP Basic username)
      limit   — number of leads to return (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    limit = int(merged.get("limit", 25))

    url = f"{CLOSE_BASE}/lead"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""), params={"_limit": limit})
        r.raise_for_status()
        data = r.json()

    leads = data.get("data", data)
    log.info("close.list_leads", count=len(leads) if isinstance(leads, list) else None)
    return {"leads": leads, "has_more": data.get("has_more", False)}


@register_node("close.create_lead")
async def close_create_lead(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new lead in Close CRM.

    config/input_data:
      api_key — Close API key (required)
      name    — lead/company name (required)
      email   — contact email address
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    name = merged.get("name") or ""
    email = merged.get("email") or ""

    if not name:
        raise ValueError("name is required for close.create_lead")

    url = f"{CLOSE_BASE}/lead"
    payload: dict = {"name": name}
    if email:
        payload["contacts"] = [{"emails": [{"email": email}]}]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, auth=(api_key, ""), json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("close.create_lead", name=name, id=data.get("id"))
    return {"lead": data, "id": data.get("id")}


@register_node("close.list_activities")
async def close_list_activities(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recent activities from Close CRM.

    config/input_data:
      api_key — Close API key (required)
      limit   — number of activities to return (default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    limit = int(merged.get("limit", 25))

    url = f"{CLOSE_BASE}/activity"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""), params={"_limit": limit})
        r.raise_for_status()
        data = r.json()

    activities = data.get("data", data)
    log.info("close.list_activities", count=len(activities) if isinstance(activities, list) else None)
    return {"activities": activities, "has_more": data.get("has_more", False)}


@register_node("close.create_activity_note")
async def close_create_activity_note(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a note activity on a lead in Close CRM.

    config/input_data:
      api_key — Close API key (required)
      lead_id — lead ID to attach the note to (required)
      note    — note text (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    lead_id = merged.get("lead_id") or ""
    text = merged.get("note") or merged.get("text") or ""

    if not lead_id:
        raise ValueError("lead_id is required for close.create_activity_note")
    if not text:
        raise ValueError("note is required for close.create_activity_note")

    url = f"{CLOSE_BASE}/activity/note"
    payload = {"lead_id": lead_id, "note": text}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, auth=(api_key, ""), json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("close.create_activity_note", lead_id=lead_id, id=data.get("id"))
    return {"activity": data, "id": data.get("id")}
