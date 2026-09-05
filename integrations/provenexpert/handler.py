"""ProvenExpert — expert reviews and ratings integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PROVENEXPERT_BASE = "https://api.provenexpert.com"


def _params(config: dict) -> dict:
    """Build base query params with API credentials."""
    return {
        "api_key": config.get("api_key", ""),
        "api_secret": config.get("api_secret", ""),
    }


@register_node("provenexpert.get_profile")
async def provenexpert_get_profile(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the ProvenExpert profile for the authenticated account.

    config:
      api_key    — ProvenExpert API key
      api_secret — ProvenExpert API secret
    """
    params = _params(config)

    async with httpx.AsyncClient(base_url=PROVENEXPERT_BASE, timeout=30) as client:
        r = await client.get(
            "/profile",
            params=params,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        profile = r.json()

    log.info("provenexpert.get_profile")
    return {"profile": profile}


@register_node("provenexpert.list_reviews")
async def provenexpert_list_reviews(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List reviews from ProvenExpert.

    config:
      api_key    — ProvenExpert API key
      api_secret — ProvenExpert API secret
      limit      — number of reviews to return (default 25)
    """
    params = _params(config)
    params["limit"] = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=PROVENEXPERT_BASE, timeout=30) as client:
        r = await client.get(
            "/reviews",
            params=params,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    reviews = data.get("reviews", data if isinstance(data, list) else [])
    log.info("provenexpert.list_reviews", count=len(reviews))
    return {"reviews": reviews, "count": len(reviews)}
