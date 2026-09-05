"""
Lemlist cold email outreach integration.

Provides campaign management and lead operations via the Lemlist API.

Credential fields:
  - api_key : Lemlist API key (used as Basic auth password with empty username)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.lemlist.com/api"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Lemlist credential missing 'api_key'")
    # Lemlist uses Basic auth with empty username and api_key as password
    return httpx.AsyncClient(
        base_url=BASE_URL,
        auth=("", api_key),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Lemlist API error {r.status_code}: {detail}")


@register_node("lemlist.list_campaigns")
async def lemlist_list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all campaigns in Lemlist."""
    log.info("lemlist.list_campaigns")
    async with await _client(credential_id, db) as client:
        r = await client.get("/campaigns")
        _raise_for_status(r)
        data = r.json()

    return {"campaigns": data if isinstance(data, list) else data.get("campaigns", [])}


@register_node("lemlist.add_lead")
async def lemlist_add_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add a lead to a Lemlist campaign."""
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    email = config.get("email") or input_data.get("email")
    first_name = config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    company_name = config.get("company_name") or input_data.get("company_name", "")

    if not campaign_id:
        raise ValueError("lemlist.add_lead requires 'campaign_id'")
    if not email:
        raise ValueError("lemlist.add_lead requires 'email'")

    payload: dict = {"email": email}
    if first_name:
        payload["firstName"] = first_name
    if last_name:
        payload["lastName"] = last_name
    if company_name:
        payload["companyName"] = company_name

    # Merge any extra fields from input
    extra = {k: v for k, v in input_data.items()
              if k not in ("campaign_id", "email", "first_name", "last_name", "company_name")}
    payload.update(extra)

    log.info("lemlist.add_lead", campaign_id=campaign_id, email=email)
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/campaigns/{campaign_id}/leads/{email}", json=payload)
        _raise_for_status(r)
        lead = r.json()

    return {"lead": lead, "email": email, "campaign_id": campaign_id}


@register_node("lemlist.get_campaign_stats")
async def lemlist_get_campaign_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get statistics for a specific Lemlist campaign."""
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    if not campaign_id:
        raise ValueError("lemlist.get_campaign_stats requires 'campaign_id'")

    log.info("lemlist.get_campaign_stats", campaign_id=campaign_id)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/campaigns/{campaign_id}/stats")
        _raise_for_status(r)
        stats = r.json()

    return {"stats": stats, "campaign_id": campaign_id}


@register_node("lemlist.delete_lead")
async def lemlist_delete_lead(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Remove a lead from a Lemlist campaign."""
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    email = config.get("email") or input_data.get("email")

    if not campaign_id:
        raise ValueError("lemlist.delete_lead requires 'campaign_id'")
    if not email:
        raise ValueError("lemlist.delete_lead requires 'email'")

    log.info("lemlist.delete_lead", campaign_id=campaign_id, email=email)
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/campaigns/{campaign_id}/leads/{email}")
        _raise_for_status(r)

    return {"deleted": True, "email": email, "campaign_id": campaign_id}
