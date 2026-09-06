"""Workday integration — workers, organizations, positions, and requests."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _workday_base(tenant: str) -> str:
    return f"https://{tenant}.workday.com/api/v1"


def _workday_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("workday.list_workers")
async def workday_list_workers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List workers from the Workday tenant.

    config:
      tenant       — Workday tenant name (required)
      access_token — OAuth2 access token (required)
      limit        — number of results (optional, default 100)
      offset       — pagination offset (optional, default 0)
      search       — search by name (optional)
    """
    merged = {**config, **input_data}
    tenant = merged.get("tenant", "")
    access_token = merged.get("access_token", "")
    if not tenant or not access_token:
        raise ValueError("tenant and access_token are required for workday.list_workers")

    params: dict = {"limit": merged.get("limit", 100), "offset": merged.get("offset", 0)}
    if merged.get("search"):
        params["search"] = merged["search"]

    async with httpx.AsyncClient(base_url=_workday_base(tenant), timeout=30) as client:
        r = await client.get("/workers", headers=_workday_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    workers = data.get("data", data) if isinstance(data, dict) else data
    total = data.get("total") if isinstance(data, dict) else None
    log.info("workday.list_workers", tenant=tenant, count=len(workers) if isinstance(workers, list) else 1)
    return {"workers": workers, "total": total}


@register_node("workday.get_worker")
async def workday_get_worker(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific Workday worker.

    config:
      tenant       — Workday tenant name (required)
      access_token — OAuth2 access token (required)
      worker_id    — Workday worker ID (required)
    """
    merged = {**config, **input_data}
    tenant = merged.get("tenant", "")
    access_token = merged.get("access_token", "")
    worker_id = merged.get("worker_id")
    if not tenant or not access_token or not worker_id:
        raise ValueError("tenant, access_token, and worker_id are required")

    async with httpx.AsyncClient(base_url=_workday_base(tenant), timeout=30) as client:
        r = await client.get(f"/workers/{worker_id}", headers=_workday_headers(access_token))
        r.raise_for_status()
        worker = r.json()

    log.info("workday.get_worker", worker_id=worker_id)
    return {"worker": worker, "worker_id": worker_id}


@register_node("workday.list_organizations")
async def workday_list_organizations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List organizations (departments/divisions) from Workday.

    config:
      tenant       — Workday tenant name (required)
      access_token — OAuth2 access token (required)
      type         — organization type: COST_CENTER/SUPERVISORY/COMPANY (optional)
      limit        — number of results (optional, default 100)
      offset       — pagination offset (optional, default 0)
    """
    merged = {**config, **input_data}
    tenant = merged.get("tenant", "")
    access_token = merged.get("access_token", "")
    if not tenant or not access_token:
        raise ValueError("tenant and access_token are required")

    params: dict = {"limit": merged.get("limit", 100), "offset": merged.get("offset", 0)}
    if merged.get("type"):
        params["type"] = merged["type"]

    async with httpx.AsyncClient(base_url=_workday_base(tenant), timeout=30) as client:
        r = await client.get("/organizations", headers=_workday_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    organizations = data.get("data", data) if isinstance(data, dict) else data
    log.info("workday.list_organizations", tenant=tenant, count=len(organizations) if isinstance(organizations, list) else 1)
    return {"organizations": organizations, "total": data.get("total") if isinstance(data, dict) else None}


@register_node("workday.list_positions")
async def workday_list_positions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List open positions from Workday.

    config:
      tenant       — Workday tenant name (required)
      access_token — OAuth2 access token (required)
      status       — filter by status: Open/Closed (optional)
      limit        — number of results (optional, default 100)
      offset       — pagination offset (optional, default 0)
    """
    merged = {**config, **input_data}
    tenant = merged.get("tenant", "")
    access_token = merged.get("access_token", "")
    if not tenant or not access_token:
        raise ValueError("tenant and access_token are required")

    params: dict = {"limit": merged.get("limit", 100), "offset": merged.get("offset", 0)}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=_workday_base(tenant), timeout=30) as client:
        r = await client.get("/positions", headers=_workday_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    positions = data.get("data", data) if isinstance(data, dict) else data
    log.info("workday.list_positions", tenant=tenant, count=len(positions) if isinstance(positions, list) else 1)
    return {"positions": positions, "total": data.get("total") if isinstance(data, dict) else None}


@register_node("workday.submit_request")
async def workday_submit_request(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Submit a business process request to Workday (e.g. hire, terminate, transfer).

    config:
      tenant         — Workday tenant name (required)
      access_token   — OAuth2 access token (required)
      request_type   — business process type e.g. "hires", "terminateEmployee" (required)
      payload        — dict of request body data (required)
    """
    merged = {**config, **input_data}
    tenant = merged.get("tenant", "")
    access_token = merged.get("access_token", "")
    request_type = merged.get("request_type")
    payload = merged.get("payload", {})
    if not tenant or not access_token or not request_type:
        raise ValueError("tenant, access_token, and request_type are required")

    async with httpx.AsyncClient(base_url=_workday_base(tenant), timeout=30) as client:
        r = await client.post(
            f"/{request_type}",
            headers=_workday_headers(access_token),
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("workday.submit_request", request_type=request_type)
    return {"result": result, "request_type": request_type}
