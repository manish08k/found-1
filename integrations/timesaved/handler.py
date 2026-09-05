"""
TimeSaved team efficiency tracking integration.

Provides time logging, entry listing, and summary retrieval via
the TimeSaved API with Bearer token authentication.

Credential fields:
  - api_key : TimeSaved API key
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://app.timesaved.com/api/v1/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("TimeSaved credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"TimeSaved API error {r.status_code}: {detail}")


@register_node("timesaved.log_time")
async def ts_log_time(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Log a time entry in TimeSaved."""
    task_name = config.get("task_name") or input_data.get("task_name")
    duration_minutes = config.get("duration_minutes") or input_data.get("duration_minutes")
    category = config.get("category") or input_data.get("category", "")
    notes = config.get("notes") or input_data.get("notes", "")
    user_id = config.get("user_id") or input_data.get("user_id")
    date = config.get("date") or input_data.get("date")

    if not task_name:
        raise ValueError("timesaved.log_time requires 'task_name'")
    if not duration_minutes:
        raise ValueError("timesaved.log_time requires 'duration_minutes'")

    payload: dict = {
        "taskName": task_name,
        "durationMinutes": int(duration_minutes),
        "category": category,
        "notes": notes,
    }
    if user_id:
        payload["userId"] = user_id
    if date:
        payload["date"] = date

    async with await _client(credential_id, db) as client:
        r = await client.post("entries", json=payload)
        _raise_for_status(r)
        data = r.json()

    log.info("timesaved.log_time", task_name=task_name, duration=duration_minutes)
    return {"entry": data, "entry_id": data.get("id")}


@register_node("timesaved.list_entries")
async def ts_list_entries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List time entries from TimeSaved."""
    limit = int(config.get("limit") or input_data.get("limit", 20))
    page = int(config.get("page") or input_data.get("page", 1))
    user_id = config.get("user_id") or input_data.get("user_id")
    category = config.get("category") or input_data.get("category")
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date")

    params: dict = {"limit": limit, "page": page}
    if user_id:
        params["userId"] = user_id
    if category:
        params["category"] = category
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date

    async with await _client(credential_id, db) as client:
        r = await client.get("entries", params=params)
        _raise_for_status(r)
        data = r.json()

    entries = data.get("entries", data) if isinstance(data, dict) else data
    log.info("timesaved.list_entries", count=len(entries) if isinstance(entries, list) else 0)
    return {"entries": entries, "page": page, "limit": limit}


@register_node("timesaved.get_summary")
async def ts_get_summary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get time efficiency summary from TimeSaved."""
    user_id = config.get("user_id") or input_data.get("user_id")
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date")
    group_by = config.get("group_by") or input_data.get("group_by", "category")

    params: dict = {"groupBy": group_by}
    if user_id:
        params["userId"] = user_id
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date

    async with await _client(credential_id, db) as client:
        r = await client.get("summary", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("timesaved.get_summary", group_by=group_by)
    return {"summary": data}
