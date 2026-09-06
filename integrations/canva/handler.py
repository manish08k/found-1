"""Canva integration — designs, exports, and creation."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CANVA_BASE = "https://api.canva.com/rest/v1"


def _canva_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("canva.list_designs")
async def canva_list_designs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List designs for the authenticated Canva user.

    config:
      access_token — Canva OAuth access token (required)
      limit        — number of designs to return (optional, default 20)
      continuation — continuation token for pagination (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    if not access_token:
        raise ValueError("access_token is required for canva.list_designs")

    params: dict = {"limit": merged.get("limit", 20)}
    if merged.get("continuation"):
        params["continuation"] = merged["continuation"]

    async with httpx.AsyncClient(base_url=CANVA_BASE, timeout=30) as client:
        r = await client.get("/designs", headers=_canva_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    log.info("canva.list_designs", count=len(items))
    return {"designs": items, "count": len(items), "continuation": data.get("continuation")}


@register_node("canva.get_design")
async def canva_get_design(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Canva design.

    config:
      access_token — Canva OAuth access token (required)
      design_id    — design ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    design_id = merged.get("design_id")
    if not access_token or not design_id:
        raise ValueError("access_token and design_id are required for canva.get_design")

    async with httpx.AsyncClient(base_url=CANVA_BASE, timeout=30) as client:
        r = await client.get(f"/designs/{design_id}", headers=_canva_headers(access_token))
        r.raise_for_status()
        data = r.json()

    log.info("canva.get_design", design_id=design_id)
    return {"design": data.get("design", data), "design_id": design_id}


@register_node("canva.export_design")
async def canva_export_design(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Export a Canva design to a file format.

    config:
      access_token — Canva OAuth access token (required)
      design_id    — design ID to export (required)
      format       — export format: pdf/png/jpg (optional, default pdf)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    design_id = merged.get("design_id")
    export_format = merged.get("format", "pdf")
    if not access_token or not design_id:
        raise ValueError("access_token and design_id are required for canva.export_design")

    payload = {"design_id": design_id, "format": export_format}

    async with httpx.AsyncClient(base_url=CANVA_BASE, timeout=60) as client:
        r = await client.post("/exports", headers=_canva_headers(access_token), json=payload)
        r.raise_for_status()
        data = r.json()

    job = data.get("job", data)
    log.info("canva.export_design", design_id=design_id, format=export_format, job_id=job.get("id"))
    return {"job": job, "job_id": job.get("id"), "design_id": design_id, "format": export_format}


@register_node("canva.create_design")
async def canva_create_design(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Canva design.

    config:
      access_token — Canva OAuth access token (required)
      design_type  — design type preset e.g. "presentation" (optional)
      title        — design title (optional)
      width        — custom width in pixels (optional)
      height       — custom height in pixels (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    if not access_token:
        raise ValueError("access_token is required for canva.create_design")

    payload: dict = {}
    if merged.get("design_type"):
        payload["design_type"] = {"type": merged["design_type"]}
    if merged.get("title"):
        payload["title"] = merged["title"]
    if merged.get("width") and merged.get("height"):
        payload["design_type"] = {"type": "custom", "width": merged["width"], "height": merged["height"]}

    async with httpx.AsyncClient(base_url=CANVA_BASE, timeout=30) as client:
        r = await client.post("/designs", headers=_canva_headers(access_token), json=payload)
        r.raise_for_status()
        data = r.json()

    design = data.get("design", data)
    log.info("canva.create_design", design_id=design.get("id"))
    return {"design": design, "design_id": design.get("id")}
