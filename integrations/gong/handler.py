"""
Gong revenue intelligence integration.

Provides call listing, transcript retrieval, user management, and
call statistics via the Gong API v2.

Credential fields:
  - api_key    : Gong API access key
  - api_secret : Gong API access key secret

Auth: HTTP Basic — base64("{api_key}:{api_secret}") in Authorization header.
Base URL: https://us-55617.api.gong.io/v2/
"""
import base64
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

GONG_BASE = "https://us-55617.api.gong.io/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    api_secret = creds.get("api_secret")
    if not api_key:
        raise ValueError("Gong credential missing 'api_key'")
    if not api_secret:
        raise ValueError("Gong credential missing 'api_secret'")

    raw = f"{api_key}:{api_secret}".encode("utf-8")
    encoded = base64.b64encode(raw).decode("ascii")

    return httpx.AsyncClient(
        base_url=GONG_BASE,
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=60.0,  # Gong responses can be large
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(f"Gong API error {r.status_code}: {detail}")


@register_node("gong.list_calls")
async def list_calls(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List Gong calls with optional date range and cursor-based pagination."""
    from_date = config.get("from_date") or input_data.get("from_date")
    to_date = config.get("to_date") or input_data.get("to_date")
    workspace_id = config.get("workspace_id") or input_data.get("workspace_id")
    cursor = config.get("cursor") or input_data.get("cursor")

    body: dict = {}
    if from_date or to_date or workspace_id:
        body["filter"] = {}
        if from_date:
            body["filter"]["fromDateTime"] = from_date
        if to_date:
            body["filter"]["toDateTime"] = to_date
        if workspace_id:
            body["filter"]["workspaceId"] = workspace_id
    if cursor:
        body["cursor"] = cursor

    log.info("gong.list_calls", from_date=from_date, to_date=to_date)

    async with await _client(credential_id, db) as client:
        r = await client.post("/calls", json=body)
        _raise_for_status(r)
        data = r.json()

    calls = data.get("calls", [])
    next_cursor = data.get("records", {}).get("cursor")
    total = data.get("records", {}).get("totalRecords", len(calls))

    log.info("gong.list_calls.done", count=len(calls), total=total)
    return {
        "calls": calls,
        "count": len(calls),
        "total": total,
        "next_cursor": next_cursor,
    }


@register_node("gong.get_call_transcript")
async def get_call_transcript(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve the full transcript for one or more Gong calls."""
    call_ids = config.get("call_ids") or input_data.get("call_ids")
    call_id = config.get("call_id") or input_data.get("call_id")

    if call_id and not call_ids:
        call_ids = [call_id]
    if not call_ids:
        raise ValueError("'call_ids' (list) or 'call_id' (string) is required")

    if isinstance(call_ids, str):
        call_ids = [call_ids]

    log.info("gong.get_call_transcript", call_ids=call_ids)

    async with await _client(credential_id, db) as client:
        r = await client.post(
            "/calls/transcript",
            json={"filter": {"callIds": call_ids}},
        )
        _raise_for_status(r)
        data = r.json()

    transcripts = data.get("callTranscripts", [])
    log.info("gong.get_call_transcript.done", count=len(transcripts))
    return {"transcripts": transcripts, "count": len(transcripts)}


@register_node("gong.list_users")
async def list_users(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all Gong users in the workspace."""
    cursor = config.get("cursor") or input_data.get("cursor")
    include_avatars = config.get("include_avatars", False)

    params: dict = {}
    if cursor:
        params["cursor"] = cursor
    if include_avatars:
        params["includeAvatars"] = "true"

    log.info("gong.list_users")

    async with await _client(credential_id, db) as client:
        r = await client.get("/users", params=params)
        _raise_for_status(r)
        data = r.json()

    users = data.get("users", [])
    next_cursor = data.get("records", {}).get("cursor")
    total = data.get("records", {}).get("totalRecords", len(users))

    log.info("gong.list_users.done", count=len(users), total=total)
    return {
        "users": users,
        "count": len(users),
        "total": total,
        "next_cursor": next_cursor,
    }


@register_node("gong.get_call_stats")
async def get_call_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve aggregated statistics for calls within a date range.
    Returns talk ratios, interaction stats, and other engagement metrics.
    """
    from_date = config.get("from_date") or input_data.get("from_date")
    to_date = config.get("to_date") or input_data.get("to_date")
    if not from_date:
        raise ValueError("'from_date' is required (ISO 8601 format, e.g. 2024-01-01T00:00:00Z)")

    call_ids = config.get("call_ids") or input_data.get("call_ids")

    body: dict = {"filter": {"fromDateTime": from_date}}
    if to_date:
        body["filter"]["toDateTime"] = to_date
    if call_ids:
        if isinstance(call_ids, str):
            call_ids = [call_ids]
        body["filter"]["callIds"] = call_ids

    log.info("gong.get_call_stats", from_date=from_date, to_date=to_date)

    async with await _client(credential_id, db) as client:
        r = await client.post("/calls/extensive", json=body)
        _raise_for_status(r)
        data = r.json()

    calls = data.get("calls", [])
    # Extract key statistics
    stats_summary = {
        "total_calls": len(calls),
        "calls": calls,
    }

    if calls:
        durations = [
            c.get("metaData", {}).get("duration", 0)
            for c in calls
            if c.get("metaData", {}).get("duration")
        ]
        if durations:
            stats_summary["avg_duration_seconds"] = sum(durations) / len(durations)
            stats_summary["total_duration_seconds"] = sum(durations)

    log.info("gong.get_call_stats.done", total_calls=len(calls))
    return stats_summary
