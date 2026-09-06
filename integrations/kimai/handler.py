"""Kimai integration — open-source time tracking."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return config.get("base_url", "").rstrip("/") + "/api"


def _headers(config: dict) -> dict:
    return {
        "X-AUTH-USER": config.get("username", ""),
        "X-AUTH-TOKEN": config.get("api_token", ""),
        "Content-Type": "application/json",
    }


@register_node("kimai.start_timesheet")
async def kimai_start_timesheet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/timesheets", json={
            "project": merged.get("project_id", 1),
            "activity": merged.get("activity_id", 1),
            "begin": merged.get("begin", ""),
            "description": merged.get("description", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("kimai.stop_timesheet")
async def kimai_stop_timesheet(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    timesheet_id = merged.get("timesheet_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.patch(f"{_base(merged)}/timesheets/{timesheet_id}/stop")
        r.raise_for_status()
    return r.json()


@register_node("kimai.get_timesheets")
async def kimai_get_timesheets(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{_base(merged)}/timesheets", params={"size": merged.get("limit", 20)})
        r.raise_for_status()
    return {"timesheets": r.json()}
