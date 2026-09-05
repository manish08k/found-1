"""
Oura Ring health data integration.

Auth: Bearer access_token.

Credential fields:
  - access_token (str) : Oura personal access token or OAuth2 access token.

Nodes:
  - oura.get_daily_sleep      : Daily sleep data.
  - oura.get_daily_readiness  : Daily readiness scores.
  - oura.get_daily_activity   : Daily activity metrics.
  - oura.get_heart_rate       : Heart-rate time series.

Base URL: https://api.ouraring.com/v2/usercollection/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.ouraring.com/v2/usercollection/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Oura credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Oura API error {r.status_code}: {detail}")


def _date_params(config: dict, input_data: dict) -> dict:
    """Extract optional start_date / end_date params."""
    params: dict = {}
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date")
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return params


@register_node("oura.get_daily_sleep")
async def get_daily_sleep(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve daily sleep data from Oura.

    Config / input keys:
      - start_date (str) : ISO date, e.g. "2024-01-01".
      - end_date (str)   : ISO date, e.g. "2024-01-07".
    """
    params = _date_params(config, input_data)
    log.info("oura.get_daily_sleep", **params)
    async with await _client(credential_id, db) as client:
        r = await client.get("daily_sleep", params=params)
        _raise_for_status(r)
        data = r.json()

    records = data.get("data", [])
    return {"sleep_records": records, "count": len(records), "next_token": data.get("next_token")}


@register_node("oura.get_daily_readiness")
async def get_daily_readiness(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve daily readiness scores from Oura.

    Config / input keys:
      - start_date (str) : ISO date.
      - end_date (str)   : ISO date.
    """
    params = _date_params(config, input_data)
    log.info("oura.get_daily_readiness", **params)
    async with await _client(credential_id, db) as client:
        r = await client.get("daily_readiness", params=params)
        _raise_for_status(r)
        data = r.json()

    records = data.get("data", [])
    return {"readiness_records": records, "count": len(records), "next_token": data.get("next_token")}


@register_node("oura.get_daily_activity")
async def get_daily_activity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve daily activity metrics from Oura.

    Config / input keys:
      - start_date (str) : ISO date.
      - end_date (str)   : ISO date.
    """
    params = _date_params(config, input_data)
    log.info("oura.get_daily_activity", **params)
    async with await _client(credential_id, db) as client:
        r = await client.get("daily_activity", params=params)
        _raise_for_status(r)
        data = r.json()

    records = data.get("data", [])
    return {"activity_records": records, "count": len(records), "next_token": data.get("next_token")}


@register_node("oura.get_heart_rate")
async def get_heart_rate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve heart-rate time series from Oura.

    Config / input keys:
      - start_datetime (str) : ISO-8601 datetime, e.g. "2024-01-01T00:00:00".
      - end_datetime (str)   : ISO-8601 datetime.
    """
    params: dict = {}
    start_datetime = config.get("start_datetime") or input_data.get("start_datetime")
    end_datetime = config.get("end_datetime") or input_data.get("end_datetime")
    # Also accept start_date / end_date as date-only aliases
    if not start_datetime:
        start_datetime = config.get("start_date") or input_data.get("start_date")
    if not end_datetime:
        end_datetime = config.get("end_date") or input_data.get("end_date")
    if start_datetime:
        params["start_datetime"] = start_datetime
    if end_datetime:
        params["end_datetime"] = end_datetime

    log.info("oura.get_heart_rate", **params)
    async with await _client(credential_id, db) as client:
        r = await client.get("heartrate", params=params)
        _raise_for_status(r)
        data = r.json()

    records = data.get("data", [])
    return {"heart_rate_records": records, "count": len(records), "next_token": data.get("next_token")}
