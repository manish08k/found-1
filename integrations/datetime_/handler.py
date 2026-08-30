"""
Date/time nodes — parsing, formatting, arithmetic, and timezone operations.

Covers:
  now, parse, format, add, subtract, diff, compare, to_timezone,
  business_hours

Uses stdlib zoneinfo (Python 3.9+) and python-dateutil for parsing.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from dateutil import parser as du_parser

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

_UTC = ZoneInfo("UTC")


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError):
        raise ValueError(f"datetime: unknown timezone '{name}'")


def _parse_value(value: Any, fmt: str | None = None) -> datetime:
    """Parse an ISO string, unix timestamp, or strptime-formatted string."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=_UTC)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        if fmt and fmt.lower() != "auto":
            return datetime.strptime(value, fmt)
        return du_parser.parse(value)
    raise ValueError(f"datetime: cannot parse value of type {type(value).__name__}")


def _localize(dt: datetime, tz: ZoneInfo) -> datetime:
    """Attach tz to a naive datetime or convert an aware one."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _ensure_aware(dt: datetime) -> datetime:
    """Make a datetime tz-aware (assumes UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_UTC)
    return dt


def _dt_to_dict(dt: datetime) -> dict:
    """Serialise a datetime into a standard dict."""
    return {
        "iso": dt.isoformat(),
        "unix": int(dt.timestamp()),
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
        "hour": dt.hour,
        "minute": dt.minute,
        "second": dt.second,
        "weekday": dt.strftime("%A"),
        "weekday_number": dt.weekday(),  # 0=Monday
        "timezone": str(dt.tzinfo) if dt.tzinfo else "UTC",
    }


# ─── datetime.now ─────────────────────────────────────────────────────────────

@register_node("datetime.now")
async def datetime_now(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Return current datetime in the requested timezone."""
    tz_name = config.get("timezone", "UTC")
    tz = _get_tz(tz_name)
    now = datetime.now(tz=tz)
    fmt = config.get("format")
    result = _dt_to_dict(now)
    result["formatted"] = now.strftime(fmt) if fmt else now.isoformat()
    result["timezone"] = tz_name
    return result


# ─── datetime.parse ───────────────────────────────────────────────────────────

@register_node("datetime.parse")
async def datetime_parse(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse a date string into structured fields."""
    value = config.get("value") or input_data.get("value")
    if value is None:
        raise ValueError("datetime.parse: 'value' is required")
    fmt = config.get("format", "auto")
    try:
        dt = _parse_value(value, fmt)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"datetime.parse: could not parse '{value}' — {exc}") from exc
    return _dt_to_dict(dt)


# ─── datetime.format ──────────────────────────────────────────────────────────

@register_node("datetime.format")
async def datetime_format(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Format a timestamp (ISO string or unix) using a strftime format string."""
    value = config.get("value") or input_data.get("value")
    if value is None:
        raise ValueError("datetime.format: 'value' is required")
    fmt = config.get("format", "%Y-%m-%d %H:%M:%S")
    dt = _parse_value(value)
    tz_name = config.get("timezone")
    if tz_name:
        tz = _get_tz(tz_name)
        dt = _localize(_ensure_aware(dt), tz)
    return {"formatted": dt.strftime(fmt), "iso": dt.isoformat()}


# ─── datetime.add ─────────────────────────────────────────────────────────────

@register_node("datetime.add")
async def datetime_add(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Add a duration to a datetime."""
    value = config.get("value") or input_data.get("value")
    if value is None:
        raise ValueError("datetime.add: 'value' is required")
    dt = _parse_value(value)
    delta = timedelta(
        weeks=float(config.get("weeks", 0)),
        days=float(config.get("days", 0)),
        hours=float(config.get("hours", 0)),
        minutes=float(config.get("minutes", 0)),
        seconds=float(config.get("seconds", 0)),
    )
    return _dt_to_dict(dt + delta)


# ─── datetime.subtract ────────────────────────────────────────────────────────

@register_node("datetime.subtract")
async def datetime_subtract(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Subtract a duration from a datetime."""
    value = config.get("value") or input_data.get("value")
    if value is None:
        raise ValueError("datetime.subtract: 'value' is required")
    dt = _parse_value(value)
    delta = timedelta(
        weeks=float(config.get("weeks", 0)),
        days=float(config.get("days", 0)),
        hours=float(config.get("hours", 0)),
        minutes=float(config.get("minutes", 0)),
        seconds=float(config.get("seconds", 0)),
    )
    return _dt_to_dict(dt - delta)


# ─── datetime.diff ────────────────────────────────────────────────────────────

@register_node("datetime.diff")
async def datetime_diff(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Calculate the difference between two datetimes."""
    start_val = config.get("start") or input_data.get("start")
    end_val = config.get("end") or input_data.get("end")
    if start_val is None or end_val is None:
        raise ValueError("datetime.diff: 'start' and 'end' are required")

    start_dt = _ensure_aware(_parse_value(start_val))
    end_dt = _ensure_aware(_parse_value(end_val))

    delta = end_dt - start_dt
    total_seconds = delta.total_seconds()

    return {
        "total_seconds": total_seconds,
        "seconds": int(abs(total_seconds) % 60),
        "minutes": int((abs(total_seconds) // 60) % 60),
        "hours": int((abs(total_seconds) // 3600) % 24),
        "days": delta.days,
        "is_negative": total_seconds < 0,
    }


# ─── datetime.compare ─────────────────────────────────────────────────────────

@register_node("datetime.compare")
async def datetime_compare(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Compare two datetimes."""
    a_val = config.get("a") or input_data.get("a")
    b_val = config.get("b") or input_data.get("b")
    if a_val is None or b_val is None:
        raise ValueError("datetime.compare: 'a' and 'b' are required")

    a_dt = _ensure_aware(_parse_value(a_val))
    b_dt = _ensure_aware(_parse_value(b_val))

    return {
        "is_before": a_dt < b_dt,
        "is_after": a_dt > b_dt,
        "is_equal": a_dt == b_dt,
        "diff_seconds": (b_dt - a_dt).total_seconds(),
    }


# ─── datetime.to_timezone ─────────────────────────────────────────────────────

@register_node("datetime.to_timezone")
async def datetime_to_timezone(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert a datetime from one timezone to another."""
    value = config.get("value") or input_data.get("value")
    if value is None:
        raise ValueError("datetime.to_timezone: 'value' is required")

    to_tz_name = config.get("to_tz") or config.get("to_timezone", "UTC")
    from_tz_name = config.get("from_tz") or config.get("from_timezone")

    to_tz = _get_tz(to_tz_name)
    dt = _parse_value(value)

    if dt.tzinfo is None:
        src_tz = _get_tz(from_tz_name) if from_tz_name else _UTC
        dt = dt.replace(tzinfo=src_tz)

    converted = dt.astimezone(to_tz)
    result = _dt_to_dict(converted)
    result["timezone"] = to_tz_name
    return result


# ─── datetime.business_hours ──────────────────────────────────────────────────

@register_node("datetime.business_hours")
async def datetime_business_hours(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Check whether a datetime falls within configured business hours."""
    value = config.get("value") or input_data.get("value")
    if value is None:
        raise ValueError("datetime.business_hours: 'value' is required")

    tz_name = config.get("timezone", "UTC")
    tz = _get_tz(tz_name)

    dt = _ensure_aware(_parse_value(value))
    dt_local = dt.astimezone(tz)

    start_hour = float(config.get("start_hour", 9))
    end_hour = float(config.get("end_hour", 17))
    # weekdays: 0=Monday…6=Sunday; default Mon-Fri
    weekdays = config.get("weekdays", [0, 1, 2, 3, 4])

    hour_decimal = dt_local.hour + dt_local.minute / 60.0
    in_hours = start_hour <= hour_decimal < end_hour
    in_weekday = dt_local.weekday() in weekdays

    return {
        "in_business_hours": in_hours and in_weekday,
        "in_work_hours": in_hours,
        "in_workday": in_weekday,
        "local_time": dt_local.isoformat(),
        "timezone": tz_name,
        "weekday": dt_local.strftime("%A"),
    }
