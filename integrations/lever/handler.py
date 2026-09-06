"""Lever integration — ATS opportunities, postings, and notes."""
import base64
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

LEVER_BASE = "https://api.lever.co/v1"


def _lever_headers(api_key: str) -> dict:
    credentials = base64.b64encode(f"{api_key}:".encode()).decode()
    return {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}


@register_node("lever.list_opportunities")
async def lever_list_opportunities(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List candidate opportunities from Lever.

    config:
      api_key   — Lever API key (required)
      stage_id  — filter by pipeline stage ID (optional)
      archived  — include archived: true/false (optional)
      limit     — results per page (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for lever.list_opportunities")

    params: dict = {"limit": merged.get("limit", 100)}
    if merged.get("stage_id"):
        params["stage_id"] = merged["stage_id"]
    if merged.get("archived") is not None:
        params["archived"] = merged["archived"]

    async with httpx.AsyncClient(base_url=LEVER_BASE, timeout=30) as client:
        r = await client.get("/opportunities", headers=_lever_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    opportunities = data.get("data", [])
    log.info("lever.list_opportunities", count=len(opportunities))
    return {"opportunities": opportunities, "count": len(opportunities), "has_next": data.get("hasNext", False)}


@register_node("lever.get_opportunity")
async def lever_get_opportunity(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Lever opportunity by ID.

    config:
      api_key        — Lever API key (required)
      opportunity_id — opportunity ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    opportunity_id = merged.get("opportunity_id")
    if not api_key or not opportunity_id:
        raise ValueError("api_key and opportunity_id are required")

    async with httpx.AsyncClient(base_url=LEVER_BASE, timeout=30) as client:
        r = await client.get(f"/opportunities/{opportunity_id}", headers=_lever_headers(api_key))
        r.raise_for_status()
        data = r.json()

    opportunity = data.get("data", data)
    log.info("lever.get_opportunity", opportunity_id=opportunity_id)
    return {"opportunity": opportunity, "opportunity_id": opportunity_id}


@register_node("lever.create_opportunity")
async def lever_create_opportunity(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Lever opportunity (candidate application).

    config:
      api_key    — Lever API key (required)
      name       — candidate full name (required)
      emails     — list of email addresses (required)
      headline   — candidate headline/title (optional)
      phones     — list of phone dicts with type/value (optional)
      stage_id   — initial pipeline stage ID (optional)
      tags       — list of tag strings (optional)
      sources    — list of source strings (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for lever.create_opportunity")

    payload: dict = {
        "name": merged.get("name", ""),
        "emails": merged.get("emails", []),
    }
    for field in ["headline", "phones", "stage", "tags", "sources"]:
        config_key = "stage_id" if field == "stage" else field
        if merged.get(config_key):
            payload[field] = merged[config_key]

    async with httpx.AsyncClient(base_url=LEVER_BASE, timeout=30) as client:
        r = await client.post("/opportunities", headers=_lever_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()

    opportunity = data.get("data", data)
    opportunity_id = opportunity.get("id")
    log.info("lever.create_opportunity", opportunity_id=opportunity_id)
    return {"opportunity": opportunity, "opportunity_id": opportunity_id}


@register_node("lever.list_postings")
async def lever_list_postings(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List job postings from Lever.

    config:
      api_key   — Lever API key (required)
      state     — filter by posting state: published/internal/closed/draft (optional)
      team      — filter by team (optional)
      limit     — results per page (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for lever.list_postings")

    params: dict = {"limit": merged.get("limit", 100)}
    if merged.get("state"):
        params["state"] = merged["state"]
    if merged.get("team"):
        params["team"] = merged["team"]

    async with httpx.AsyncClient(base_url=LEVER_BASE, timeout=30) as client:
        r = await client.get("/postings", headers=_lever_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    postings = data.get("data", [])
    log.info("lever.list_postings", count=len(postings))
    return {"postings": postings, "count": len(postings), "has_next": data.get("hasNext", False)}


@register_node("lever.get_posting")
async def lever_get_posting(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Lever job posting by ID.

    config:
      api_key    — Lever API key (required)
      posting_id — posting ID to retrieve (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    posting_id = merged.get("posting_id")
    if not api_key or not posting_id:
        raise ValueError("api_key and posting_id are required")

    async with httpx.AsyncClient(base_url=LEVER_BASE, timeout=30) as client:
        r = await client.get(f"/postings/{posting_id}", headers=_lever_headers(api_key))
        r.raise_for_status()
        data = r.json()

    posting = data.get("data", data)
    log.info("lever.get_posting", posting_id=posting_id)
    return {"posting": posting, "posting_id": posting_id}


@register_node("lever.add_note")
async def lever_add_note(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a note to a Lever opportunity.

    config:
      api_key        — Lever API key (required)
      opportunity_id — opportunity ID to add note to (required)
      value          — note text content (required)
      score          — feedback score: thumbsup/thumbsdown/no_decision (optional)
      notify_ids     — list of user IDs to notify (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    opportunity_id = merged.get("opportunity_id")
    value = merged.get("value")
    if not api_key or not opportunity_id or not value:
        raise ValueError("api_key, opportunity_id, and value are required")

    payload: dict = {"value": value}
    if merged.get("score"):
        payload["score"] = merged["score"]
    if merged.get("notify_ids"):
        payload["notifyIds"] = merged["notify_ids"]

    async with httpx.AsyncClient(base_url=LEVER_BASE, timeout=30) as client:
        r = await client.post(
            f"/opportunities/{opportunity_id}/notes",
            headers=_lever_headers(api_key),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    note = data.get("data", data)
    note_id = note.get("id")
    log.info("lever.add_note", opportunity_id=opportunity_id, note_id=note_id)
    return {"note": note, "note_id": note_id, "opportunity_id": opportunity_id}
