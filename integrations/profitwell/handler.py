"""
ProfitWell subscription analytics integration.

Provides subscription data, customer listing, MRR metrics, and churn
analysis via the ProfitWell API v2.

Credential fields:
  - api_key : ProfitWell Private API Key (found in ProfitWell Settings > API).

Auth: api_key sent as the value of the Authorization header (no Bearer prefix).
Base URL: https://api.profitwell.com/v2/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.profitwell.com/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("ProfitWell credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": api_key,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ProfitWell API error {r.status_code}: {detail}")


@register_node("profitwell.get_subscription")
async def profitwell_get_subscription(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve a single subscription by subscription ID.

    Params:
      - subscription_id (required): The ProfitWell subscription ID or external ID.
    """
    subscription_id = config.get("subscription_id") or input_data.get("subscription_id")
    if not subscription_id:
        raise ValueError("profitwell.get_subscription requires 'subscription_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/subscriptions/{subscription_id}/")
        _raise_for_status(r)
        data = r.json()

    log.info("profitwell.get_subscription", subscription_id=subscription_id)
    return {"subscription": data}


@register_node("profitwell.list_customers")
async def profitwell_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List customers/subscribers.

    Params:
      - email: Filter customers by email address.
      - user_alias: Filter by external user alias / customer ID.
      - limit: Maximum number of results to return (default 50).
      - offset: Pagination offset (default 0).
    """
    params: dict = {}

    email = config.get("email") or input_data.get("email")
    if email:
        params["email"] = email

    user_alias = config.get("user_alias") or input_data.get("user_alias")
    if user_alias:
        params["user_alias"] = user_alias

    limit = config.get("limit") or input_data.get("limit")
    if limit is not None:
        params["limit"] = int(limit)

    offset = config.get("offset") or input_data.get("offset")
    if offset is not None:
        params["offset"] = int(offset)

    async with await _client(credential_id, db) as client:
        r = await client.get("/customers/", params=params)
        _raise_for_status(r)
        data = r.json()

    customers = data if isinstance(data, list) else data.get("customers", data)
    log.info("profitwell.list_customers", count=len(customers) if isinstance(customers, list) else None)
    return {"customers": customers, "raw": data}


@register_node("profitwell.get_metrics")
async def profitwell_get_metrics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve MRR/ARR and other subscription metrics for a date range.

    Params:
      - month (required): Month in YYYY-MM format (e.g. '2024-01').  Used for
        monthly aggregate metrics.
      - daily: bool — if True, fetch daily breakdown instead of monthly aggregate.
    """
    month = config.get("month") or input_data.get("month")
    if not month:
        raise ValueError("profitwell.get_metrics requires 'month' (YYYY-MM)")

    daily = config.get("daily") or input_data.get("daily", False)
    endpoint = "/metrics/mrr/" if not daily else "/metrics/mrr/daily/"

    params = {"month": month}

    async with await _client(credential_id, db) as client:
        r = await client.get(endpoint, params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("profitwell.get_metrics", month=month)
    return {"metrics": data}


@register_node("profitwell.get_churn")
async def profitwell_get_churn(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve churn data (revenue churn and customer churn).

    Params:
      - month (required): Month in YYYY-MM format.
      - type: 'revenue' or 'customers' (default 'revenue').
    """
    month = config.get("month") or input_data.get("month")
    if not month:
        raise ValueError("profitwell.get_churn requires 'month' (YYYY-MM)")

    churn_type = config.get("type") or input_data.get("type", "revenue")
    endpoint = f"/metrics/churn/{churn_type}/"

    params = {"month": month}

    async with await _client(credential_id, db) as client:
        r = await client.get(endpoint, params=params)
        _raise_for_status(r)
        data = r.json()

    log.info("profitwell.get_churn", month=month, type=churn_type)
    return {"churn": data, "type": churn_type, "month": month}
