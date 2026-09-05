"""Baremetrics integration — SaaS metrics and customer analytics."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BAREMETRICS_BASE = "https://api.baremetrics.com/v1"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


@register_node("baremetrics.list_metrics")
async def baremetrics_list_metrics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Baremetrics summary metrics for a date range.

    config:
      api_key    — Baremetrics API key (required)
      start_date — Start date in YYYY-MM-DD format (required)
      end_date   — End date in YYYY-MM-DD format (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date")

    if not api_key:
        raise ValueError("api_key is required for baremetrics.list_metrics")
    if not start_date:
        raise ValueError("start_date is required for baremetrics.list_metrics")
    if not end_date:
        raise ValueError("end_date is required for baremetrics.list_metrics")

    async with httpx.AsyncClient(base_url=BAREMETRICS_BASE, timeout=30) as client:
        r = await client.get(
            "/metrics",
            headers=_headers(api_key),
            params={"start_date": start_date, "end_date": end_date},
        )
        r.raise_for_status()
        data = r.json()

    metrics = data.get("metrics", data)
    log.info("baremetrics.list_metrics", start_date=start_date, end_date=end_date)
    return {"metrics": metrics, "start_date": start_date, "end_date": end_date}


@register_node("baremetrics.get_metric")
async def baremetrics_get_metric(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Baremetrics metric for a date range.

    config:
      api_key    — Baremetrics API key (required)
      metric     — Metric name e.g. "mrr", "arr", "ltv" (required)
      start_date — Start date in YYYY-MM-DD format (required)
      end_date   — End date in YYYY-MM-DD format (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    metric = config.get("metric") or input_data.get("metric", "mrr")
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date")

    if not api_key:
        raise ValueError("api_key is required for baremetrics.get_metric")
    if not start_date:
        raise ValueError("start_date is required for baremetrics.get_metric")
    if not end_date:
        raise ValueError("end_date is required for baremetrics.get_metric")

    async with httpx.AsyncClient(base_url=BAREMETRICS_BASE, timeout=30) as client:
        r = await client.get(
            f"/metrics/{metric}",
            headers=_headers(api_key),
            params={"start_date": start_date, "end_date": end_date},
        )
        r.raise_for_status()
        data = r.json()

    log.info("baremetrics.get_metric", metric=metric, start_date=start_date, end_date=end_date)
    return {"metric": metric, "data": data, "start_date": start_date, "end_date": end_date}


@register_node("baremetrics.list_customers")
async def baremetrics_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Baremetrics customers.

    config:
      api_key — Baremetrics API key (required)
      limit   — Number of customers to return (default 25)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for baremetrics.list_customers")
    limit = int(config.get("limit", 25))

    async with httpx.AsyncClient(base_url=BAREMETRICS_BASE, timeout=30) as client:
        r = await client.get("/customers", headers=_headers(api_key), params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    customers = data.get("customers", [])
    log.info("baremetrics.list_customers", count=len(customers))
    return {"customers": customers, "count": len(customers), "meta": data.get("meta", {})}
