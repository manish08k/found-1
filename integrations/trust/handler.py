"""Trust reviews and testimonial platform — handler for trust integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.trust.co/v1"


@register_node("trust.list_reviews")
async def trust_list_reviews(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List reviews.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/reviews", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("trust.list_reviews")
    return {"data": data}

@register_node("trust.create_review_request")
async def trust_create_review_request(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a review request.

    config/input_data:
      api_key — API key or token (required)
      email — (required)
      name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    email = merged.get("email") or ""
    name = merged.get("name") or ""
    if not email or not name:
        raise ValueError("email, name required for trust.create_review_request")
    payload = {"email": email, "name": name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/review-requests", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("trust.create_review_request")
    return {"data": data}

@register_node("trust.get_review")
async def trust_get_review(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a review.

    config/input_data:
      api_key — API key or token (required)
      review_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    review_id = merged.get("review_id") or ""
    if not review_id:
        raise ValueError("review_id required for trust.get_review")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/reviews/{review_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("trust.get_review")
    return {"data": data}
