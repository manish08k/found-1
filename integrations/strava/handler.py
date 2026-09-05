"""Strava integration — fitness tracking (Bearer OAuth access_token)."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

STRAVA_BASE = "https://www.strava.com/api/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds["access_token"]
    return httpx.AsyncClient(
        base_url=STRAVA_BASE,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        timeout=30,
    )


@register_node("strava.get_athlete")
async def strava_get_athlete(config: dict, input_data: dict, credential_id: str, db) -> dict:
    log.info("strava.get_athlete")
    async with await _client(credential_id, db) as client:
        r = await client.get("/athlete")
        r.raise_for_status()
        data = r.json()

    return {
        "athlete_id": data.get("id"),
        "firstname": data.get("firstname"),
        "lastname": data.get("lastname"),
        "username": data.get("username"),
        "city": data.get("city"),
        "country": data.get("country"),
        "profile": data.get("profile"),
        "raw": data,
    }


@register_node("strava.list_activities")
async def strava_list_activities(config: dict, input_data: dict, credential_id: str, db) -> dict:
    page = config.get("page", 1)
    per_page = config.get("per_page", 30)
    before = config.get("before") or input_data.get("before")  # Unix timestamp
    after = config.get("after") or input_data.get("after")     # Unix timestamp

    params: dict = {"page": page, "per_page": per_page}
    if before:
        params["before"] = before
    if after:
        params["after"] = after

    log.info("strava.list_activities", page=page, per_page=per_page)
    async with await _client(credential_id, db) as client:
        r = await client.get("/athlete/activities", params=params)
        r.raise_for_status()
        data = r.json()

    return {"activities": data, "count": len(data), "page": page}


@register_node("strava.get_activity")
async def strava_get_activity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    activity_id = config.get("activity_id") or input_data.get("activity_id", "")
    include_all_efforts = config.get("include_all_efforts", False)

    log.info("strava.get_activity", activity_id=activity_id)
    async with await _client(credential_id, db) as client:
        r = await client.get(
            f"/activities/{activity_id}",
            params={"include_all_efforts": include_all_efforts},
        )
        r.raise_for_status()
        data = r.json()

    return {
        "activity_id": data.get("id"),
        "name": data.get("name"),
        "type": data.get("type"),
        "distance": data.get("distance"),
        "moving_time": data.get("moving_time"),
        "elapsed_time": data.get("elapsed_time"),
        "start_date": data.get("start_date"),
        "raw": data,
    }


@register_node("strava.create_activity")
async def strava_create_activity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    name = config.get("name") or input_data.get("name", "")
    sport_type = config.get("sport_type") or input_data.get("sport_type", "Run")
    start_date_local = config.get("start_date_local") or input_data.get("start_date_local", "")
    elapsed_time = config.get("elapsed_time") or input_data.get("elapsed_time", 0)
    description = config.get("description") or input_data.get("description", "")
    distance = config.get("distance") or input_data.get("distance")
    trainer = config.get("trainer", False)
    commute = config.get("commute", False)

    payload: dict = {
        "name": name,
        "sport_type": sport_type,
        "start_date_local": start_date_local,
        "elapsed_time": elapsed_time,
        "description": description,
        "trainer": int(trainer),
        "commute": int(commute),
    }
    if distance is not None:
        payload["distance"] = distance

    log.info("strava.create_activity", name=name, sport_type=sport_type)
    async with await _client(credential_id, db) as client:
        r = await client.post("/activities", json=payload)
        r.raise_for_status()
        data = r.json()

    return {
        "activity_id": data.get("id"),
        "name": data.get("name"),
        "type": data.get("type"),
        "start_date": data.get("start_date"),
    }
