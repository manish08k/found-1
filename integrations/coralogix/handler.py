"""Coralogix log management integration — send and query logs."""
import time
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

CORALOGIX_INGRESS_BASE = "https://ingress.coralogix.com/logs/v1"
CORALOGIX_QUERY_URL = "https://ng-api-http.coralogix.com/api/v1/dataprime/query"


def _api_key(config: dict, input_data: dict) -> str:
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required")
    return api_key


@register_node("coralogix.send_logs")
async def coralogix_send_logs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send log entries to Coralogix.

    config/input_data:
      api_key          — Coralogix private key (required)
      app_name         — application name (required)
      subsystem_name   — subsystem name (required)
      message          — log message text (required)
      severity         — log severity 1-6 (default 3 = INFO)
    """
    api_key = _api_key(config, input_data)
    app_name = config.get("app_name") or input_data.get("app_name")
    subsystem_name = config.get("subsystem_name") or input_data.get("subsystem_name")
    message = config.get("message") or input_data.get("message")
    severity = int(config.get("severity", 3))

    if not app_name:
        raise ValueError("app_name is required")
    if not subsystem_name:
        raise ValueError("subsystem_name is required")
    if not message:
        raise ValueError("message is required")

    timestamp_ms = int(time.time() * 1000)
    payload = {
        "privateKey": api_key,
        "applicationName": app_name,
        "subsystemName": subsystem_name,
        "logEntries": [
            {
                "timestamp": timestamp_ms,
                "severity": severity,
                "text": message,
            }
        ],
    }

    async with httpx.AsyncClient(base_url=CORALOGIX_INGRESS_BASE, timeout=30) as client:
        r = await client.post("/singles", json=payload)
        r.raise_for_status()

    log.info("coralogix.send_logs", app=app_name, subsystem=subsystem_name)
    return {
        "sent": True,
        "app_name": app_name,
        "subsystem_name": subsystem_name,
        "timestamp": timestamp_ms,
    }


@register_node("coralogix.query_logs")
async def coralogix_query_logs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Query logs from Coralogix using DataPrime.

    config/input_data:
      api_key — Coralogix API key (required)
      query   — DataPrime query string (required)
    """
    api_key = _api_key(config, input_data)
    query_str = config.get("query") or input_data.get("query")
    if not query_str:
        raise ValueError("query is required")

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"query": query_str}

    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        r = await client.post(CORALOGIX_QUERY_URL, json=payload)
        r.raise_for_status()
        data = r.json()

    results = data.get("results", data)
    log.info("coralogix.query_logs", query=query_str)
    return {"results": results, "query": query_str}
