"""Google My Business integration — accounts, locations, and reviews."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GMB_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
GMB_REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"


def _headers(config: dict, input_data: dict) -> dict:
    token = config.get("access_token") or input_data.get("access_token")
    if not token:
        raise ValueError("access_token is required")
    return {"Authorization": f"Bearer {token}"}


@register_node("google_my_business.list_accounts")
async def gmb_list_accounts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Google My Business accounts.

    config:
      access_token — OAuth2 access token (required)
    """
    headers = _headers(config, input_data)

    async with httpx.AsyncClient(base_url=GMB_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/accounts")
        r.raise_for_status()
        data = r.json()

    accounts = data.get("accounts", [])
    log.info("google_my_business.list_accounts", count=len(accounts))
    return {"accounts": accounts, "count": len(accounts)}


@register_node("google_my_business.list_locations")
async def gmb_list_locations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List locations for a Google My Business account.

    config/input_data:
      access_token — OAuth2 access token (required)
      account_id   — GMB account ID (required)
    """
    headers = _headers(config, input_data)
    account_id = config.get("account_id") or input_data.get("account_id")
    if not account_id:
        raise ValueError("account_id is required")

    async with httpx.AsyncClient(base_url=GMB_BASE, headers=headers, timeout=30) as client:
        r = await client.get(f"/accounts/{account_id}/locations")
        r.raise_for_status()
        data = r.json()

    locations = data.get("locations", [])
    log.info("google_my_business.list_locations", account_id=account_id, count=len(locations))
    return {"locations": locations, "count": len(locations), "account_id": account_id}


@register_node("google_my_business.get_reviews")
async def gmb_get_reviews(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get reviews for a Google My Business location.

    config/input_data:
      access_token — OAuth2 access token (required)
      account_id   — GMB account ID (required)
      location_id  — GMB location ID (required)
    """
    headers = _headers(config, input_data)
    account_id = config.get("account_id") or input_data.get("account_id")
    location_id = config.get("location_id") or input_data.get("location_id")
    if not account_id:
        raise ValueError("account_id is required")
    if not location_id:
        raise ValueError("location_id is required")

    url = f"{GMB_REVIEWS_BASE}/accounts/{account_id}/locations/{location_id}/reviews"

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

    reviews = data.get("reviews", [])
    log.info("google_my_business.get_reviews", account_id=account_id, location_id=location_id, count=len(reviews))
    return {
        "reviews": reviews,
        "count": len(reviews),
        "account_id": account_id,
        "location_id": location_id,
    }
