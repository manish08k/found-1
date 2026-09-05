"""Assembled — workforce management integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ASSEMBLED_BASE = "https://api.assembledhq.com/api/v0"


def _headers(config: dict) -> dict:
    api_key = config.get("api_key", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("assembled.list_agents")
async def assembled_list_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List support agents from Assembled.

    config:
      api_key — Assembled API key
    """
    async with httpx.AsyncClient(base_url=ASSEMBLED_BASE, timeout=30) as client:
        r = await client.get("/agents", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    agents = data.get("agents", data if isinstance(data, list) else [])
    log.info("assembled.list_agents", count=len(agents))
    return {"agents": agents, "count": len(agents)}


@register_node("assembled.get_schedule")
async def assembled_get_schedule(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get agent schedules from Assembled for a date range.

    config/input_data:
      api_key    — Assembled API key
      start_date — schedule start date in YYYY-MM-DD format (required)
      end_date   — schedule end date in YYYY-MM-DD format (required)
    """
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date")

    if not start_date:
        raise ValueError("start_date is required for assembled.get_schedule")
    if not end_date:
        raise ValueError("end_date is required for assembled.get_schedule")

    async with httpx.AsyncClient(base_url=ASSEMBLED_BASE, timeout=30) as client:
        r = await client.get(
            "/schedules",
            params={"start_date": start_date, "end_date": end_date},
            headers=_headers(config),
        )
        r.raise_for_status()
        data = r.json()

    schedules = data.get("schedules", data if isinstance(data, list) else [])
    log.info("assembled.get_schedule", start_date=start_date, end_date=end_date, count=len(schedules))
    return {"schedules": schedules, "count": len(schedules), "start_date": start_date, "end_date": end_date}


@register_node("assembled.list_queues")
async def assembled_list_queues(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List support queues from Assembled.

    config:
      api_key — Assembled API key
    """
    async with httpx.AsyncClient(base_url=ASSEMBLED_BASE, timeout=30) as client:
        r = await client.get("/queues", headers=_headers(config))
        r.raise_for_status()
        data = r.json()

    queues = data.get("queues", data if isinstance(data, list) else [])
    log.info("assembled.list_queues", count=len(queues))
    return {"queues": queues, "count": len(queues)}
