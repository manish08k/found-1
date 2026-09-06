"""Time Operations integration — time zone conversion and date utilities."""
import httpx
import structlog
from core.execution_engine import register_node
from datetime import datetime, timezone
import pytz

log = structlog.get_logger(__name__)


@register_node("time_ops.convert_timezone")
async def time_ops_convert_timezone(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    dt_str = merged.get("datetime", "")
    from_tz = merged.get("from_timezone", "UTC")
    to_tz = merged.get("to_timezone", "UTC")
    try:
        from_zone = pytz.timezone(from_tz)
        to_zone = pytz.timezone(to_tz)
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = from_zone.localize(dt)
        converted = dt.astimezone(to_zone)
        return {"converted": converted.isoformat(), "timezone": to_tz}
    except Exception as e:
        return {"error": str(e)}


@register_node("time_ops.get_current_time")
async def time_ops_get_current_time(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    tz_name = merged.get("timezone", "UTC")
    try:
        import pytz
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        return {"current_time": now.isoformat(), "timezone": tz_name, "unix": int(now.timestamp())}
    except Exception as e:
        return {"error": str(e)}


@register_node("time_ops.add_duration")
async def time_ops_add_duration(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    from datetime import timedelta
    dt_str = merged.get("datetime", "")
    days = int(merged.get("days", 0))
    hours = int(merged.get("hours", 0))
    minutes = int(merged.get("minutes", 0))
    try:
        dt = datetime.fromisoformat(dt_str)
        result = dt + timedelta(days=days, hours=hours, minutes=minutes)
        return {"result": result.isoformat()}
    except Exception as e:
        return {"error": str(e)}
