"""Intruder integration — vulnerability scanning targets and scans."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

INTRUDER_BASE = "https://api.intruder.io/v1"


def _intruder_headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("intruder.list_targets")
async def intruder_list_targets(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all targets in the Intruder account.

    config:
      api_key — Intruder API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    async with httpx.AsyncClient(base_url=INTRUDER_BASE, timeout=30) as client:
        r = await client.get("/targets", headers=_intruder_headers(api_key))
        r.raise_for_status()
        data = r.json()

    targets = data.get("targets", data) if isinstance(data, dict) else data
    count = len(targets) if isinstance(targets, list) else 0
    log.info("intruder.list_targets", count=count)
    return {"targets": targets, "count": count}


@register_node("intruder.get_target")
async def intruder_get_target(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get details of a specific Intruder target.

    config:
      api_key   — Intruder API key (required)
      target_id — target ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    target_id = merged.get("target_id")
    if not target_id:
        raise ValueError("target_id is required for intruder.get_target")

    async with httpx.AsyncClient(base_url=INTRUDER_BASE, timeout=30) as client:
        r = await client.get(f"/targets/{target_id}", headers=_intruder_headers(api_key))
        r.raise_for_status()
        target = r.json()

    log.info("intruder.get_target", target_id=target_id)
    return {"target": target, "target_id": target_id}


@register_node("intruder.list_scans")
async def intruder_list_scans(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List all scans in the Intruder account.

    config:
      api_key — Intruder API key (required)
      status  — filter by scan status (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    params: dict = {}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=INTRUDER_BASE, timeout=30) as client:
        r = await client.get(
            "/scans", headers=_intruder_headers(api_key), params=params
        )
        r.raise_for_status()
        data = r.json()

    scans = data.get("scans", data) if isinstance(data, dict) else data
    count = len(scans) if isinstance(scans, list) else 0
    log.info("intruder.list_scans", count=count)
    return {"scans": scans, "count": count}


@register_node("intruder.get_scan")
async def intruder_get_scan(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get details of a specific Intruder scan.

    config:
      api_key — Intruder API key (required)
      scan_id — scan ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    scan_id = merged.get("scan_id")
    if not scan_id:
        raise ValueError("scan_id is required for intruder.get_scan")

    async with httpx.AsyncClient(base_url=INTRUDER_BASE, timeout=30) as client:
        r = await client.get(f"/scans/{scan_id}", headers=_intruder_headers(api_key))
        r.raise_for_status()
        scan = r.json()

    log.info("intruder.get_scan", scan_id=scan_id, status=scan.get("status"))
    return {"scan": scan, "scan_id": scan_id}


@register_node("intruder.start_scan")
async def intruder_start_scan(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Start a new vulnerability scan for a target.

    config:
      api_key   — Intruder API key (required)
      target_id — target ID to scan (required)
      scan_type — type of scan e.g. "scheduled" or "manual" (optional, default "manual")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    target_id = merged.get("target_id")
    if not target_id:
        raise ValueError("target_id is required for intruder.start_scan")

    payload: dict = {
        "target_id": target_id,
        "scan_type": merged.get("scan_type", "manual"),
    }

    async with httpx.AsyncClient(base_url=INTRUDER_BASE, timeout=30) as client:
        r = await client.post(
            "/scans", headers=_intruder_headers(api_key), json=payload
        )
        r.raise_for_status()
        scan = r.json()

    log.info("intruder.start_scan", target_id=target_id, scan_id=scan.get("id"))
    return {"scan": scan, "scan_id": scan.get("id"), "target_id": target_id}
