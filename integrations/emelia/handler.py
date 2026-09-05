"""
Emelia cold email outreach integration.

Manages campaigns, contacts, and analytics for Emelia cold email sequences.

Credential fields:
  - api_key : Emelia API key (sent as Bearer token)

Base URL: https://app.emelia.io/api/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://app.emelia.io/api"


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Emelia API error {r.status_code}: {detail}")


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key", "").strip()
    if not api_key:
        raise ValueError("Emelia credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=30.0,
    )


@register_node("emelia.list_campaigns")
async def list_campaigns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List all cold email campaigns in the Emelia account.

    Config / input keys:
      - page     (int) : Page number (1-based). Default 1.
      - per_page (int) : Items per page. Default 20.

    Returns:
      { "campaigns": [...], "total": int, "page": int }
    """
    page = int(config.get("page") or input_data.get("page", 1))
    per_page = min(int(config.get("per_page") or input_data.get("per_page", 20)), 100)

    log.info("emelia.list_campaigns", page=page, per_page=per_page)

    async with await _client(credential_id, db) as client:
        r = await client.get(
            "/campaigns",
            params={"page": page, "per_page": per_page},
        )
        _raise_for_status(r)
        data = r.json()

    campaigns = data.get("campaigns", data if isinstance(data, list) else [])
    return {
        "campaigns": campaigns,
        "total": data.get("total", len(campaigns)),
        "page": page,
        "per_page": per_page,
    }


@register_node("emelia.start_campaign")
async def start_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Start (or resume) an Emelia campaign.

    Config / input keys:
      - campaign_id (str) : Required. Campaign ID to start.

    Returns:
      { "campaign_id": str, "status": str, "started": bool }
    """
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    if not campaign_id:
        raise ValueError("emelia.start_campaign requires 'campaign_id'")

    log.info("emelia.start_campaign", campaign_id=campaign_id)

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/campaigns/{campaign_id}/start")
        _raise_for_status(r)
        data = r.json()

    return {
        "campaign_id": campaign_id,
        "status": data.get("status", "running"),
        "started": True,
        "raw": data,
    }


@register_node("emelia.add_contact")
async def add_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Add a contact to an Emelia campaign.

    Config / input keys:
      - campaign_id  (str)  : Required. Target campaign ID.
      - email        (str)  : Required. Contact email.
      - first_name   (str)  : Contact first name.
      - last_name    (str)  : Contact last name.
      - company_name (str)  : Contact company.
      - custom_fields (dict): Any additional merge variables.

    Returns:
      { "contact_id": str, "email": str, "campaign_id": str }
    """
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    email = config.get("email") or input_data.get("email")

    if not campaign_id:
        raise ValueError("emelia.add_contact requires 'campaign_id'")
    if not email:
        raise ValueError("emelia.add_contact requires 'email'")

    payload: dict = {"email": email}

    for field in ("first_name", "last_name", "company_name"):
        val = config.get(field) or input_data.get(field)
        if val:
            payload[field] = val

    custom_fields = config.get("custom_fields") or input_data.get("custom_fields", {})
    if custom_fields and isinstance(custom_fields, dict):
        payload.update(custom_fields)

    log.info("emelia.add_contact", campaign_id=campaign_id, email=email)

    async with await _client(credential_id, db) as client:
        r = await client.post(
            f"/campaigns/{campaign_id}/contacts",
            json=payload,
        )
        _raise_for_status(r)
        data = r.json()

    return {
        "contact_id": data.get("id", data.get("contact_id")),
        "email": email,
        "campaign_id": campaign_id,
        "raw": data,
    }


@register_node("emelia.get_stats")
async def get_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve performance statistics for an Emelia campaign.

    Config / input keys:
      - campaign_id (str) : Required. Campaign ID to fetch stats for.

    Returns:
      {
        "campaign_id": str,
        "sent": int,
        "opened": int,
        "clicked": int,
        "replied": int,
        "bounced": int,
        "open_rate": float,
        "click_rate": float,
        "reply_rate": float
      }
    """
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    if not campaign_id:
        raise ValueError("emelia.get_stats requires 'campaign_id'")

    log.info("emelia.get_stats", campaign_id=campaign_id)

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/campaigns/{campaign_id}/stats")
        _raise_for_status(r)
        data = r.json()

    stats = data.get("stats", data)
    sent = int(stats.get("sent", 0))

    def _rate(n: int) -> float:
        return round(n / sent * 100, 2) if sent else 0.0

    opened = int(stats.get("opened", stats.get("opens", 0)))
    clicked = int(stats.get("clicked", stats.get("clicks", 0)))
    replied = int(stats.get("replied", stats.get("replies", 0)))
    bounced = int(stats.get("bounced", stats.get("bounces", 0)))

    return {
        "campaign_id": campaign_id,
        "sent": sent,
        "opened": opened,
        "clicked": clicked,
        "replied": replied,
        "bounced": bounced,
        "open_rate": _rate(opened),
        "click_rate": _rate(clicked),
        "reply_rate": _rate(replied),
        "bounce_rate": _rate(bounced),
    }
