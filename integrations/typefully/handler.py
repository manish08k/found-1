"""Typefully Twitter threads integration — drafts, scheduling."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TYPEFULLY_BASE = "https://api.typefully.com/v1"


def _headers(api_key: str) -> dict:
    return {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }


@register_node("typefully.create_draft")
async def typefully_create_draft(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a Typefully draft.

    config/input_data:
      api_key    — Typefully API key (required)
      content    — draft text content (required)
      threadify  — automatically split into thread (default: False)
      share      — make draft shareable (default: False)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for typefully.create_draft")
    content = config.get("content") or input_data.get("content")
    if not content:
        raise ValueError("content is required for typefully.create_draft")

    payload = {
        "content": content,
        "threadify": bool(config.get("threadify", False)),
        "share": bool(config.get("share", False)),
    }

    async with httpx.AsyncClient(base_url=TYPEFULLY_BASE, timeout=30) as client:
        r = await client.post("/drafts/", headers=_headers(api_key), json=payload)
        r.raise_for_status()
        draft = r.json()

    log.info("typefully.create_draft", draft_id=draft.get("id"))
    return {"draft": draft, "draft_id": draft.get("id")}


@register_node("typefully.schedule_draft")
async def typefully_schedule_draft(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create and schedule a Typefully draft for a specific date/time.

    config/input_data:
      api_key        — Typefully API key (required)
      content        — draft text content (required)
      schedule_date  — ISO 8601 datetime string for scheduled send (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for typefully.schedule_draft")
    content = config.get("content") or input_data.get("content")
    if not content:
        raise ValueError("content is required for typefully.schedule_draft")
    schedule_date = config.get("schedule_date") or input_data.get("schedule_date")
    if not schedule_date:
        raise ValueError("schedule_date is required for typefully.schedule_draft")

    payload = {"content": content, "schedule-date": schedule_date}

    async with httpx.AsyncClient(base_url=TYPEFULLY_BASE, timeout=30) as client:
        r = await client.post("/drafts/", headers=_headers(api_key), json=payload)
        r.raise_for_status()
        draft = r.json()

    log.info("typefully.schedule_draft", draft_id=draft.get("id"), scheduled=schedule_date)
    return {"draft": draft, "draft_id": draft.get("id"), "scheduled_for": schedule_date}


@register_node("typefully.list_scheduled_drafts")
async def typefully_list_scheduled_drafts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List scheduled Typefully drafts.

    config/input_data:
      api_key — Typefully API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for typefully.list_scheduled_drafts")

    async with httpx.AsyncClient(base_url=TYPEFULLY_BASE, timeout=30) as client:
        r = await client.get("/drafts/", headers=_headers(api_key), params={"filter": "scheduled"})
        r.raise_for_status()
        data = r.json()

    drafts = data if isinstance(data, list) else data.get("drafts", data.get("data", []))
    log.info("typefully.list_scheduled_drafts", count=len(drafts))
    return {"drafts": drafts, "count": len(drafts)}
