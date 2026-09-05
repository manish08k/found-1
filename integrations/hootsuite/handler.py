"""Hootsuite social management integration — profiles, messages."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

HOOTSUITE_BASE = "https://platform.hootsuite.com/v1"


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


@register_node("hootsuite.list_social_profiles")
async def hootsuite_list_social_profiles(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Hootsuite social profiles for the authenticated user.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for hootsuite.list_social_profiles")

    async with httpx.AsyncClient(base_url=HOOTSUITE_BASE, timeout=30) as client:
        r = await client.get("/socialProfiles", headers=_headers(access_token))
        r.raise_for_status()
        data = r.json()

    profiles = data.get("data", [])
    log.info("hootsuite.list_social_profiles", count=len(profiles))
    return {"profiles": profiles, "count": len(profiles)}


@register_node("hootsuite.schedule_message")
async def hootsuite_schedule_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Schedule a Hootsuite social media message.

    config/input_data:
      access_token         — OAuth2 Bearer token (required)
      text                 — message text (required)
      social_profile_id    — social profile ID to post to (required)
      scheduled_send_time  — ISO 8601 datetime string for sending (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for hootsuite.schedule_message")
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("text is required for hootsuite.schedule_message")
    social_profile_id = config.get("social_profile_id") or input_data.get("social_profile_id")
    if not social_profile_id:
        raise ValueError("social_profile_id is required for hootsuite.schedule_message")
    scheduled_send_time = config.get("scheduled_send_time") or input_data.get("scheduled_send_time")
    if not scheduled_send_time:
        raise ValueError("scheduled_send_time is required for hootsuite.schedule_message")

    payload = {
        "text": text,
        "socialProfileIds": [social_profile_id],
        "scheduledSendTime": scheduled_send_time,
    }

    async with httpx.AsyncClient(base_url=HOOTSUITE_BASE, timeout=30) as client:
        r = await client.post("/messages", headers=_headers(access_token), json=payload)
        r.raise_for_status()
        result = r.json()

    data = result.get("data", result)
    log.info("hootsuite.schedule_message", message_id=data.get("id"))
    return {"message": data, "message_id": data.get("id")}


@register_node("hootsuite.list_messages")
async def hootsuite_list_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Hootsuite scheduled/sent messages.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      limit        — max number of messages to return (default 25)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for hootsuite.list_messages")
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=HOOTSUITE_BASE, timeout=30) as client:
        r = await client.get("/messages", headers=_headers(access_token), params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    messages = data.get("data", [])
    log.info("hootsuite.list_messages", count=len(messages))
    return {"messages": messages, "count": len(messages)}
