"""
Beeminder goal-tracking integration.

Provides goal listing/retrieval, datapoint creation, and goal updating
via the Beeminder API v1.

Credential fields:
  - username : Beeminder username (without @).
  - api_key  : Beeminder Personal Auth Token (found in Account Settings > Apps & API).

Auth: api_key passed as query parameter on every request.
Base URL: https://www.beeminder.com/api/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://www.beeminder.com/api/v1"


async def _get_creds(credential_id: str, db) -> tuple[str, str]:
    creds = await get_credential_data(credential_id, db)
    username = creds.get("username")
    api_key = creds.get("api_key")
    if not username:
        raise ValueError("Beeminder credential missing 'username'")
    if not api_key:
        raise ValueError("Beeminder credential missing 'api_key'")
    return username, api_key


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Beeminder API error {r.status_code}: {detail}")


@register_node("beeminder.list_goals")
async def bm_list_goals(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all goals for the authenticated user.

    Params:
      - filter: 'frontburner', 'backburner', or omit for all.
    """
    username, api_key = await _get_creds(credential_id, db)
    goal_filter = config.get("filter") or input_data.get("filter")

    params: dict = {"auth_token": api_key}
    if goal_filter:
        params["filter"] = goal_filter

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get(f"/users/{username}/goals.json", params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("beeminder.list_goals", username=username, count=len(data))
    return {"goals": data, "count": len(data)}


@register_node("beeminder.get_goal")
async def bm_get_goal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve details of a single goal.

    Params:
      - goal_slug (required): The URL slug of the goal (e.g., 'weight').
      - datapoints: bool — include recent datapoints in response.
    """
    username, api_key = await _get_creds(credential_id, db)
    goal_slug = config.get("goal_slug") or input_data.get("goal_slug")
    if not goal_slug:
        raise ValueError("beeminder.get_goal requires 'goal_slug'")

    params: dict = {"auth_token": api_key}
    if config.get("datapoints") or input_data.get("datapoints"):
        params["datapoints"] = "true"

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get(f"/users/{username}/goals/{goal_slug}.json", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"goal": data, "slug": goal_slug, "rate": data.get("rate"), "deadline": data.get("deadline")}


@register_node("beeminder.create_datapoint")
async def bm_create_datapoint(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Add a new datapoint to a Beeminder goal.

    Params:
      - goal_slug (required): The URL slug of the goal.
      - value (required): Numeric value of the datapoint.
      - timestamp: Unix timestamp for the datapoint (default: now).
      - comment: Optional text comment.
      - requestid: Unique string to prevent duplicate submissions.
    """
    username, api_key = await _get_creds(credential_id, db)
    goal_slug = config.get("goal_slug") or input_data.get("goal_slug")
    value = config.get("value") if config.get("value") is not None else input_data.get("value")
    if not goal_slug:
        raise ValueError("beeminder.create_datapoint requires 'goal_slug'")
    if value is None:
        raise ValueError("beeminder.create_datapoint requires 'value'")

    payload: dict = {
        "auth_token": api_key,
        "value": float(value),
    }

    timestamp = config.get("timestamp") or input_data.get("timestamp")
    if timestamp:
        payload["timestamp"] = timestamp

    comment = config.get("comment") or input_data.get("comment")
    if comment:
        payload["comment"] = comment

    requestid = config.get("requestid") or input_data.get("requestid")
    if requestid:
        payload["requestid"] = requestid

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.post(
            f"/users/{username}/goals/{goal_slug}/datapoints.json",
            data=payload,
        )
        _raise_for_status(r)
        data = r.json()

    log.info("beeminder.create_datapoint", goal=goal_slug, value=value, id=data.get("id"))
    return {"datapoint": data, "id": data.get("id"), "value": data.get("value")}


@register_node("beeminder.update_goal")
async def bm_update_goal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update settings for an existing goal.

    Params:
      - goal_slug (required): The URL slug of the goal.
      - rate: New weekly rate (numeric).
      - goaldate: New goal due date as Unix timestamp.
      - goalval: New goal value.
      - panic: Seconds before derailment to send panic alerts.
    """
    username, api_key = await _get_creds(credential_id, db)
    goal_slug = config.get("goal_slug") or input_data.get("goal_slug")
    if not goal_slug:
        raise ValueError("beeminder.update_goal requires 'goal_slug'")

    payload: dict = {"auth_token": api_key}

    for field in ("rate", "goaldate", "goalval", "panic"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val

    if len(payload) == 1:
        raise ValueError("beeminder.update_goal requires at least one field to update (rate, goaldate, goalval, panic)")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.put(
            f"/users/{username}/goals/{goal_slug}.json",
            data=payload,
        )
        _raise_for_status(r)
        data = r.json()

    log.info("beeminder.update_goal", goal=goal_slug)
    return {"goal": data}


@register_node("beeminder.list_datapoints")
async def bm_list_datapoints(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List datapoints for a goal, sorted by time.

    Params:
      - goal_slug (required): The URL slug of the goal.
      - sort: 'id', 'updated_at', 'daystamp' (default 'daystamp').
      - count: Max number of datapoints to return.
    """
    username, api_key = await _get_creds(credential_id, db)
    goal_slug = config.get("goal_slug") or input_data.get("goal_slug")
    if not goal_slug:
        raise ValueError("beeminder.list_datapoints requires 'goal_slug'")

    params: dict = {"auth_token": api_key}
    sort = config.get("sort") or input_data.get("sort", "daystamp")
    params["sort"] = sort
    count = config.get("count") or input_data.get("count")
    if count:
        params["count"] = int(count)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get(
            f"/users/{username}/goals/{goal_slug}/datapoints.json",
            params=params,
        )
        _raise_for_status(r)
        data = r.json()

    return {"datapoints": data, "count": len(data)}
