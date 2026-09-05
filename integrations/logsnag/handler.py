"""LogSnag integration — event tracking and monitoring via LogSnag API v1."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

LOGSNAG_BASE = "https://api.logsnag.com/v1"


def _headers(config: dict, input_data: dict) -> dict:
    merged = {**config, **input_data}
    return {"Authorization": f"Bearer {merged.get('api_token', merged.get('api_key', ''))}"}


@register_node("logsnag.log")
async def log_event(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Log an event to a LogSnag channel.

    config/input_data:
      api_token   — LogSnag API token (required)
      project     — LogSnag project name (required)
      channel     — LogSnag channel name (required)
      event       — Event name (required)
      description — Event description (optional)
      icon        — Emoji icon (optional, default: rocket)
      notify      — Send push notification (optional, default: False)
    """
    merged = {**config, **input_data}
    project = merged.get("project", "")
    channel = merged.get("channel", "")
    event = merged.get("event", "")
    if not project or not channel or not event:
        raise ValueError("project, channel, and event are required for logsnag.log")
    headers = _headers(config, input_data)
    payload = {
        "project": project,
        "channel": channel,
        "event": event,
        "description": merged.get("description", ""),
        "icon": merged.get("icon", "🚀"),
        "notify": bool(merged.get("notify", False)),
    }
    async with httpx.AsyncClient(base_url=LOGSNAG_BASE, timeout=30) as client:
        r = await client.post("/log", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json() if r.text else {}
    log.info("logsnag.log", project=project, channel=channel, event=event)
    return {"result": data, "project": project, "channel": channel, "event": event}


@register_node("logsnag.insight")
async def insight(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Post an insight metric to LogSnag.

    config/input_data:
      api_token — LogSnag API token (required)
      project   — LogSnag project name (required)
      title     — Insight title (required)
      value     — Insight value (required)
      icon      — Emoji icon (optional, default: chart)
    """
    merged = {**config, **input_data}
    project = merged.get("project", "")
    title = merged.get("title", "")
    value = merged.get("value", "")
    if not project or not title or value == "":
        raise ValueError("project, title, and value are required for logsnag.insight")
    headers = _headers(config, input_data)
    payload = {
        "project": project,
        "title": title,
        "value": value,
        "icon": merged.get("icon", "📊"),
    }
    async with httpx.AsyncClient(base_url=LOGSNAG_BASE, timeout=30) as client:
        r = await client.post("/insight", json=payload, headers=headers)
        r.raise_for_status()
        data = r.json() if r.text else {}
    log.info("logsnag.insight", project=project, title=title, value=value)
    return {"result": data, "project": project, "title": title, "value": value}
