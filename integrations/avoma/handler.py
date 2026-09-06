"""Avoma AI meeting assistant — handler for avoma integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.avoma.com/v1"


@register_node("avoma.list_meetings")
async def avoma_list_meetings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List meetings.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/meetings", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("avoma.list_meetings")
    return {"data": data}

@register_node("avoma.get_meeting")
async def avoma_get_meeting(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get meeting details.

    config/input_data:
      api_key — API key or token (required)
      meeting_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    meeting_id = merged.get("meeting_id") or ""
    if not meeting_id:
        raise ValueError("meeting_id required for avoma.get_meeting")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/meetings/{meeting_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("avoma.get_meeting")
    return {"data": data}

@register_node("avoma.get_transcript")
async def avoma_get_transcript(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get meeting transcript.

    config/input_data:
      api_key — API key or token (required)
      meeting_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    meeting_id = merged.get("meeting_id") or ""
    if not meeting_id:
        raise ValueError("meeting_id required for avoma.get_transcript")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/meetings/{meeting_id}/transcript", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("avoma.get_transcript")
    return {"data": data}
