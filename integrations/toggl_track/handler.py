"""Toggl Track time tracking — handler for toggl_track integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.track.toggl.com/api/v9"


@register_node("toggl_track.list_time_entries")
async def toggl_track_list_time_entries(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List time entries.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/me/time_entries", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("toggl_track.list_time_entries")
    return {"data": data}

@register_node("toggl_track.create_time_entry")
async def toggl_track_create_time_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a time entry.

    config/input_data:
      api_key — API key or token (required)
      workspace_id — (required)
      start — (required)
      duration — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    workspace_id = merged.get("workspace_id") or ""
    start = merged.get("start") or ""
    duration = merged.get("duration") or ""
    if not workspace_id or not start or not duration:
        raise ValueError("workspace_id, start, duration required for toggl_track.create_time_entry")
    payload = {"start": start, "duration": duration}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/workspaces/{workspace_id}/time_entries", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("toggl_track.create_time_entry")
    return {"data": data}

@register_node("toggl_track.get_current_entry")
async def toggl_track_get_current_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get current running entry.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/me/time_entries/current", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("toggl_track.get_current_entry")
    return {"data": data}

@register_node("toggl_track.stop_time_entry")
async def toggl_track_stop_time_entry(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Stop a running entry.

    config/input_data:
      api_key — API key or token (required)
      workspace_id — (required)
      entry_id — (required)
    """
    merged = {**config, **input_data}
    username = merged.get("username") or merged.get("api_key") or ""
    password = merged.get("password") or merged.get("api_token") or ""
    import base64
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}
    workspace_id = merged.get("workspace_id") or ""
    entry_id = merged.get("entry_id") or ""
    if not workspace_id or not entry_id:
        raise ValueError("workspace_id, entry_id required for toggl_track.stop_time_entry")
    payload = merged
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(f"{BASE_URL}/workspaces/{workspace_id}/time_entries/{entry_id}/stop", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("toggl_track.stop_time_entry")
    return {"data": data}
