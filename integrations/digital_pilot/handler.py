"""
Digital Pilot integration — digital marketing automation.

Credential fields:
  - api_key: Digital Pilot API key
  - base_url: API base URL (default: https://api.digitalpilot.io/v1)

Auth: Bearer token via Authorization header
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

DEFAULT_BASE_URL = "https://api.digitalpilot.io/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Digital Pilot credential missing 'api_key'")
    base_url = creds.get("base_url", DEFAULT_BASE_URL).rstrip("/")
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Digital Pilot API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok"}


@register_node("digital_pilot.run_campaign")
async def digital_pilot_run_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /campaigns — launch a marketing campaign."""
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    name = config.get("name") or input_data.get("name")
    body: dict = {}
    if campaign_id:
        body["campaign_id"] = campaign_id
    if name:
        body["name"] = name
    for field in ("audience", "budget", "schedule", "channels"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.post("/campaigns", json=body)
    return _check(r)


@register_node("digital_pilot.get_report")
async def digital_pilot_get_report(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /campaigns/{id}/report — get campaign analytics report."""
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    if not campaign_id:
        raise ValueError("digital_pilot.get_report requires 'campaign_id'")
    params = {}
    date_from = config.get("date_from") or input_data.get("date_from")
    if date_from:
        params["date_from"] = date_from
    date_to = config.get("date_to") or input_data.get("date_to")
    if date_to:
        params["date_to"] = date_to
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/campaigns/{campaign_id}/report", params=params)
    return _check(r)


@register_node("digital_pilot.list_campaigns")
async def digital_pilot_list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /campaigns — list all campaigns."""
    params = {}
    status = config.get("status") or input_data.get("status")
    if status:
        params["status"] = status
    async with await _client(credential_id, db) as client:
        r = await client.get("/campaigns", params=params)
    return _check(r)


@register_node("digital_pilot.update_campaign")
async def digital_pilot_update_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PATCH /campaigns/{id} — update a campaign."""
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    if not campaign_id:
        raise ValueError("digital_pilot.update_campaign requires 'campaign_id'")
    body: dict = {}
    for field in ("name", "status", "budget", "audience", "schedule"):
        v = config.get(field) or input_data.get(field)
        if v is not None:
            body[field] = v
    async with await _client(credential_id, db) as client:
        r = await client.patch(f"/campaigns/{campaign_id}", json=body)
    return _check(r)
