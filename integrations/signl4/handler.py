"""
SIGNL4 mobile alerting integration.

Credential fields:
  - team_secret: SIGNL4 team secret (embedded in the webhook URL)

Auth: team_secret in URL — https://connect.signl4.com/webhook/{team_secret}
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://connect.signl4.com/webhook"


async def _get_team_secret(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    team_secret = creds.get("team_secret")
    if not team_secret:
        raise ValueError("SIGNL4 credential missing 'team_secret'")
    return team_secret


def _raise_for_status(r: httpx.Response) -> dict:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"SIGNL4 API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    try:
        return r.json()
    except Exception:
        return {"response": r.text}


@register_node("signl4.send_alert")
async def signl4_send_alert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a mobile alert via SIGNL4."""
    team_secret = await _get_team_secret(credential_id, db)

    title = config.get("title") or input_data.get("title", "Alert")
    message = config.get("message") or input_data.get("message", "")
    severity = config.get("severity") or input_data.get("severity", "")
    filtering = config.get("filtering") or input_data.get("filtering", False)
    alert_id = config.get("alert_id") or input_data.get("alert_id", "")
    # Additional custom fields
    extra = config.get("extra") or input_data.get("extra", {})

    payload: dict = {
        "Title": title,
        "Message": message,
    }
    if severity:
        payload["Severity"] = severity
    if filtering:
        payload["Filtering"] = filtering
    if alert_id:
        payload["X-S2-ExternalID"] = str(alert_id)
    if isinstance(extra, dict):
        payload.update(extra)

    log.info("signl4.send_alert", title=title)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{_BASE_URL}/{team_secret}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
    data = _raise_for_status(r)
    return {"success": True, "response": data, "title": title}


@register_node("signl4.resolve_alert")
async def signl4_resolve_alert(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Resolve (close) an existing SIGNL4 alert by external ID."""
    team_secret = await _get_team_secret(credential_id, db)

    alert_id = config.get("alert_id") or input_data.get("alert_id")
    if not alert_id:
        raise ValueError("signl4.resolve_alert requires 'alert_id'")

    payload = {
        "X-S2-ExternalID": str(alert_id),
        "X-S2-Status": "resolved",
    }

    log.info("signl4.resolve_alert", alert_id=alert_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{_BASE_URL}/{team_secret}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
    data = _raise_for_status(r)
    return {"success": True, "response": data, "alert_id": alert_id, "status": "resolved"}
