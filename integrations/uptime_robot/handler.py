"""
UptimeRobot monitoring integration.

Credential fields:
  - api_key: UptimeRobot API key

Auth: POST body param api_key with format=json
Base URL: https://api.uptimerobot.com/v2
Note: UptimeRobot uses POST for all endpoints with form data.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

UPTIMEROBOT_BASE_URL = "https://api.uptimerobot.com/v2"


async def _get_api_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("UptimeRobot credential is missing 'api_key'")
    return api_key


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"UptimeRobot API error {r.status_code}: {detail}")
    data = r.json()
    if data.get("stat") == "fail":
        error = data.get("error", {})
        raise ValueError(f"UptimeRobot API error: {error}")
    return data


async def _post(api_key: str, endpoint: str, extra: dict = None) -> dict:
    """Helper to POST to UptimeRobot API with form data."""
    form_data = {"api_key": api_key, "format": "json"}
    if extra:
        form_data.update(extra)
    async with httpx.AsyncClient(base_url=UPTIMEROBOT_BASE_URL, timeout=30.0) as client:
        r = await client.post(
            endpoint,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        )
    return _check(r)


# ---------------------------------------------------------------------------
# Monitors
# ---------------------------------------------------------------------------

@register_node("uptime_robot.list_monitors")
async def uptime_robot_list_monitors(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /getMonitors — list all monitors."""
    api_key = await _get_api_key(credential_id, db)
    extra: dict = {}
    monitors = config.get("monitors") or input_data.get("monitors")
    if monitors:
        extra["monitors"] = monitors if isinstance(monitors, str) else "-".join(str(m) for m in monitors)
    statuses = config.get("statuses") or input_data.get("statuses")
    if statuses:
        extra["statuses"] = statuses
    search = config.get("search") or input_data.get("search")
    if search:
        extra["search"] = search
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        extra["limit"] = int(limit)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        extra["offset"] = int(offset)
    return await _post(api_key, "/getMonitors", extra)


@register_node("uptime_robot.get_monitor")
async def uptime_robot_get_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /getMonitors — get a specific monitor by ID."""
    api_key = await _get_api_key(credential_id, db)
    monitor_id = config.get("monitor_id") or input_data.get("monitor_id")
    if not monitor_id:
        raise ValueError("uptime_robot.get_monitor requires 'monitor_id'")
    return await _post(api_key, "/getMonitors", {"monitors": str(monitor_id)})


@register_node("uptime_robot.add_monitor")
async def uptime_robot_add_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /newMonitor — create a new monitor."""
    api_key = await _get_api_key(credential_id, db)
    friendly_name = config.get("friendly_name") or input_data.get("friendly_name")
    url = config.get("url") or input_data.get("url")
    monitor_type = config.get("type") or input_data.get("type")
    if not friendly_name or not url or not monitor_type:
        raise ValueError("uptime_robot.add_monitor requires 'friendly_name', 'url', and 'type'")
    extra: dict = {
        "friendly_name": friendly_name,
        "url": url,
        "type": str(monitor_type),
    }
    for field in ("sub_type", "keyword_type", "keyword_value", "interval", "alert_contacts"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            extra[field] = str(v)
    return await _post(api_key, "/newMonitor", extra)


@register_node("uptime_robot.edit_monitor")
async def uptime_robot_edit_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /editMonitor — edit an existing monitor."""
    api_key = await _get_api_key(credential_id, db)
    monitor_id = config.get("monitor_id") or input_data.get("monitor_id")
    if not monitor_id:
        raise ValueError("uptime_robot.edit_monitor requires 'monitor_id'")
    extra: dict = {"id": str(monitor_id)}
    for field in ("friendly_name", "url", "type", "sub_type", "keyword_type", "keyword_value", "interval", "status"):
        v = config.get(field)
        if v is None:
            v = input_data.get(field)
        if v is not None:
            extra[field] = str(v)
    return await _post(api_key, "/editMonitor", extra)


@register_node("uptime_robot.delete_monitor")
async def uptime_robot_delete_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /deleteMonitor — delete a monitor."""
    api_key = await _get_api_key(credential_id, db)
    monitor_id = config.get("monitor_id") or input_data.get("monitor_id")
    if not monitor_id:
        raise ValueError("uptime_robot.delete_monitor requires 'monitor_id'")
    return await _post(api_key, "/deleteMonitor", {"id": str(monitor_id)})


@register_node("uptime_robot.reset_monitor")
async def uptime_robot_reset_monitor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /resetMonitor — reset a monitor's statistics."""
    api_key = await _get_api_key(credential_id, db)
    monitor_id = config.get("monitor_id") or input_data.get("monitor_id")
    if not monitor_id:
        raise ValueError("uptime_robot.reset_monitor requires 'monitor_id'")
    return await _post(api_key, "/resetMonitor", {"id": str(monitor_id)})


# ---------------------------------------------------------------------------
# Alert Contacts
# ---------------------------------------------------------------------------

@register_node("uptime_robot.list_alert_contacts")
async def uptime_robot_list_alert_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /getAlertContacts — list all alert contacts."""
    api_key = await _get_api_key(credential_id, db)
    extra: dict = {}
    alert_contacts = config.get("alert_contacts") or input_data.get("alert_contacts")
    if alert_contacts:
        extra["alert_contacts"] = str(alert_contacts)
    limit = config.get("limit") or input_data.get("limit")
    if limit:
        extra["limit"] = int(limit)
    offset = config.get("offset") or input_data.get("offset")
    if offset:
        extra["offset"] = int(offset)
    return await _post(api_key, "/getAlertContacts", extra)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

@register_node("uptime_robot.get_account_details")
async def uptime_robot_get_account_details(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /getAccountDetails — get account details and usage."""
    api_key = await _get_api_key(credential_id, db)
    return await _post(api_key, "/getAccountDetails")


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test UptimeRobot connection by fetching account details."""
    api_key = await _get_api_key(credential_id, db)
    data = await _post(api_key, "/getAccountDetails")
    account = data.get("account", {})
    return {"ok": True, "email": account.get("email", "unknown"), "monitor_limit": account.get("monitor_limit")}
