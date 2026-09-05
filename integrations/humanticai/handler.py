"""
Humantic AI integration — personality insights and sales intelligence.

Provides profile creation, retrieval, and sales-focused insights via the
Humantic AI API v1.

Credential fields:
  - api_key : Humantic AI API key (Bearer token auth)

Base URL: https://api.humantic.ai/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.humantic.ai/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("humanticai credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Humantic AI API error {r.status_code}: {detail}")


@register_node("humanticai.create_profile")
async def humantic_create_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a personality profile for a user.

    Config / input_data fields:
      - user_id (required) : LinkedIn URL, email, or a unique identifier
      - texts              : list of text samples for analysis (optional)
      - send_email         : whether to send email to the user (bool, optional)
    """
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("humanticai.create_profile requires 'user_id'")

    texts = config.get("texts") or input_data.get("texts", [])
    send_email = config.get("send_email") or input_data.get("send_email", False)

    payload: dict = {"id": user_id}
    if texts:
        payload["texts"] = texts if isinstance(texts, list) else [texts]
    if send_email:
        payload["send_email"] = send_email

    log.info("humanticai.create_profile", user_id=user_id)
    async with await _client(credential_id, db) as client:
        r = await client.post("/user-persona/create", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"profile": data, "user_id": user_id}


@register_node("humanticai.get_profile")
async def humantic_get_profile(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve an existing personality profile.

    Config / input_data fields:
      - user_id (required) : the identifier used when creating the profile
      - persona            : persona type filter, e.g. 'sales' (optional)
    """
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("humanticai.get_profile requires 'user_id'")

    persona = config.get("persona") or input_data.get("persona", "")

    params: dict = {"id": user_id}
    if persona:
        params["persona"] = persona

    log.info("humanticai.get_profile", user_id=user_id)
    async with await _client(credential_id, db) as client:
        r = await client.get("/user-persona", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"profile": data, "user_id": user_id}


@register_node("humanticai.get_sales_insights")
async def humantic_get_sales_insights(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve sales-focused personality insights for a user.

    Config / input_data fields:
      - user_id (required) : the identifier used when creating the profile
    """
    user_id = config.get("user_id") or input_data.get("user_id")
    if not user_id:
        raise ValueError("humanticai.get_sales_insights requires 'user_id'")

    log.info("humanticai.get_sales_insights", user_id=user_id)
    async with await _client(credential_id, db) as client:
        r = await client.get("/user-persona", params={"id": user_id, "persona": "sales"})
        _raise_for_status(r)
        data = r.json()

    # Extract the sales-specific section if present
    results = data.get("results", data)
    sales_insights = results.get("sales", results) if isinstance(results, dict) else results

    return {
        "user_id": user_id,
        "sales_insights": sales_insights,
        "raw": data,
    }
