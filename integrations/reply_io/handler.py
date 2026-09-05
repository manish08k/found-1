"""Reply.io sales automation integration — people and campaigns."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

REPLY_IO_BASE = "https://api.reply.io/v1"


@register_node("reply_io.list_people")
async def reply_io_list_people(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List people from Reply.io.

    config/input_data:
      api_key — Reply.io API key (required)
      limit   — number of people to return (default 100)
      skip    — number of records to skip (default 0)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    limit = int(merged.get("limit", 100))
    skip = int(merged.get("skip", 0))

    headers = {"X-Api-Key": api_key}
    url = f"{REPLY_IO_BASE}/people"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"limit": limit, "skip": skip})
        r.raise_for_status()
        data = r.json()

    people = data if isinstance(data, list) else data.get("people", data)
    log.info("reply_io.list_people", count=len(people) if isinstance(people, list) else None)
    return {"people": people}


@register_node("reply_io.add_person")
async def reply_io_add_person(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a new person to Reply.io.

    config/input_data:
      api_key    — Reply.io API key (required)
      first_name — first name (required)
      last_name  — last name
      email      — email address (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""

    if not fn:
        raise ValueError("first_name is required for reply_io.add_person")
    if not email:
        raise ValueError("email is required for reply_io.add_person")

    headers = {"X-Api-Key": api_key}
    url = f"{REPLY_IO_BASE}/people"
    payload = {"firstName": fn, "lastName": ln, "email": email}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("reply_io.add_person", email=email)
    return {"person": data}


@register_node("reply_io.push_to_campaign")
async def reply_io_push_to_campaign(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Push a person to a campaign in Reply.io.

    config/input_data:
      api_key     — Reply.io API key (required)
      email       — person email (required)
      campaign_id — campaign ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    email = merged.get("email") or ""
    campaign_id = merged.get("campaign_id") or merged.get("campaignId")

    if not email:
        raise ValueError("email is required for reply_io.push_to_campaign")
    if not campaign_id:
        raise ValueError("campaign_id is required for reply_io.push_to_campaign")

    headers = {"X-Api-Key": api_key}
    url = f"{REPLY_IO_BASE}/people/pushToCampaign"
    payload = {"email": email, "campaignId": campaign_id}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("reply_io.push_to_campaign", email=email, campaign_id=campaign_id)
    return {"result": data}


@register_node("reply_io.list_campaigns")
async def reply_io_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List campaigns from Reply.io.

    config/input_data:
      api_key — Reply.io API key (required)
      limit   — number of campaigns to return (default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    limit = int(merged.get("limit", 100))

    headers = {"X-Api-Key": api_key}
    url = f"{REPLY_IO_BASE}/campaigns"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    campaigns = data if isinstance(data, list) else data.get("campaigns", data)
    log.info("reply_io.list_campaigns", count=len(campaigns) if isinstance(campaigns, list) else None)
    return {"campaigns": campaigns}
