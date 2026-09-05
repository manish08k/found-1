"""Streak CRM integration — pipelines, boxes, and contacts."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

STREAK_BASE = "https://www.streak.com/api/v1"


@register_node("streak.list_pipelines")
async def streak_list_pipelines(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Streak pipelines.

    config/input_data:
      api_key — Streak API key (required, used as HTTP Basic username)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    url = f"{STREAK_BASE}/pipelines"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""))
        r.raise_for_status()
        data = r.json()

    log.info("streak.list_pipelines", count=len(data) if isinstance(data, list) else None)
    return {"pipelines": data}


@register_node("streak.get_pipeline")
async def streak_get_pipeline(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Streak pipeline by key.

    config/input_data:
      api_key      — Streak API key (required)
      pipeline_key — pipeline key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    pipeline_key = merged.get("pipeline_key") or ""

    if not pipeline_key:
        raise ValueError("pipeline_key is required for streak.get_pipeline")

    url = f"{STREAK_BASE}/pipelines/{pipeline_key}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""))
        r.raise_for_status()
        data = r.json()

    log.info("streak.get_pipeline", pipeline_key=pipeline_key)
    return {"pipeline": data}


@register_node("streak.list_boxes")
async def streak_list_boxes(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List boxes (deals) in a Streak pipeline.

    config/input_data:
      api_key      — Streak API key (required)
      pipeline_key — pipeline key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    pipeline_key = merged.get("pipeline_key") or ""

    if not pipeline_key:
        raise ValueError("pipeline_key is required for streak.list_boxes")

    url = f"{STREAK_BASE}/pipelines/{pipeline_key}/boxes"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""))
        r.raise_for_status()
        data = r.json()

    log.info("streak.list_boxes", pipeline_key=pipeline_key, count=len(data) if isinstance(data, list) else None)
    return {"boxes": data, "pipeline_key": pipeline_key}


@register_node("streak.create_box")
async def streak_create_box(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new box (deal) in a Streak pipeline.

    config/input_data:
      api_key      — Streak API key (required)
      pipeline_key — pipeline key (required)
      name         — box name (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    pipeline_key = merged.get("pipeline_key") or ""
    name = merged.get("name") or ""

    if not pipeline_key:
        raise ValueError("pipeline_key is required for streak.create_box")
    if not name:
        raise ValueError("name is required for streak.create_box")

    url = f"{STREAK_BASE}/pipelines/{pipeline_key}/boxes"
    payload = {"name": name}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, auth=(api_key, ""), json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("streak.create_box", pipeline_key=pipeline_key, name=name, key=data.get("key"))
    return {"box": data, "key": data.get("key")}


@register_node("streak.list_contacts")
async def streak_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all contacts in Streak.

    config/input_data:
      api_key — Streak API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    url = f"{STREAK_BASE}/contacts"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""))
        r.raise_for_status()
        data = r.json()

    log.info("streak.list_contacts", count=len(data) if isinstance(data, list) else None)
    return {"contacts": data}
