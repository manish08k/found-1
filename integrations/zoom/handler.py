"""
Zoom integration — meetings, participants, recordings.
Nodes: zoom.create_meeting, zoom.get_meeting, zoom.list_meetings,
       zoom.delete_meeting, zoom.get_recordings
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

ZOOM_API = "https://api.zoom.us/v2"


async def _zoom_token(config: dict) -> str:
    """Get OAuth2 access token via Server-to-Server OAuth (account credentials)."""
    account_id = config.get("account_id") or getattr(settings, "ZOOM_ACCOUNT_ID", "")
    client_id = config.get("client_id") or getattr(settings, "ZOOM_CLIENT_ID", "")
    client_secret = config.get("client_secret") or getattr(settings, "ZOOM_CLIENT_SECRET", "")

    if not all([account_id, client_id, client_secret]):
        raise ValueError("zoom nodes require ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://zoom.us/oauth/token",
            params={"grant_type": "account_credentials", "account_id": account_id},
            auth=(client_id, client_secret),
        )
        r.raise_for_status()
        return r.json()["access_token"]


@register_node("zoom.create_meeting")
async def zoom_create_meeting(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _zoom_token(merged)
    user_id = merged.get("user_id", "me")

    payload = {
        "topic": merged.get("topic", "New Meeting"),
        "type": int(merged.get("type", 2)),  # 1=instant, 2=scheduled
        "start_time": merged.get("start_time"),
        "duration": int(merged.get("duration", 60)),
        "timezone": merged.get("timezone", "UTC"),
        "agenda": merged.get("agenda", ""),
        "settings": {
            "host_video": merged.get("host_video", True),
            "participant_video": merged.get("participant_video", True),
            "join_before_host": merged.get("join_before_host", False),
            "mute_upon_entry": merged.get("mute_upon_entry", False),
            "waiting_room": merged.get("waiting_room", True),
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{ZOOM_API}/users/{user_id}/meetings",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    return {
        "id": data.get("id"),
        "topic": data.get("topic"),
        "join_url": data.get("join_url"),
        "start_time": data.get("start_time"),
        "duration": data.get("duration"),
        "password": data.get("password"),
    }


@register_node("zoom.get_meeting")
async def zoom_get_meeting(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _zoom_token(merged)
    meeting_id = merged.get("meeting_id")
    if not meeting_id:
        raise ValueError("zoom.get_meeting requires 'meeting_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{ZOOM_API}/meetings/{meeting_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()

    return {"meeting": r.json()}


@register_node("zoom.list_meetings")
async def zoom_list_meetings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _zoom_token(merged)
    user_id = merged.get("user_id", "me")
    meeting_type = merged.get("type", "scheduled")
    page_size = min(int(merged.get("page_size", 30)), 300)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{ZOOM_API}/users/{user_id}/meetings",
            params={"type": meeting_type, "page_size": page_size},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    return {"meetings": data.get("meetings", []), "total_records": data.get("total_records", 0)}


@register_node("zoom.delete_meeting")
async def zoom_delete_meeting(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _zoom_token(merged)
    meeting_id = merged.get("meeting_id")
    if not meeting_id:
        raise ValueError("zoom.delete_meeting requires 'meeting_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.delete(
            f"{ZOOM_API}/meetings/{meeting_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()

    return {"ok": True, "deleted": meeting_id}


@register_node("zoom.get_recordings")
async def zoom_get_recordings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    token = await _zoom_token(merged)
    user_id = merged.get("user_id", "me")
    from_date = merged.get("from_date", "")
    to_date = merged.get("to_date", "")

    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{ZOOM_API}/users/{user_id}/recordings",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        data = r.json()

    return {"meetings": data.get("meetings", []), "total_records": data.get("total_records", 0)}
