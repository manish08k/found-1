"""Schedule integration — cron/interval based trigger node.

No credentials required.

Nodes:
  - schedule.trigger : evaluate schedule configuration and return timing info

Config:
  - trigger_at_hour   : hour(s) to trigger (int 0-23 or list)
  - trigger_at_minute : minute(s) to trigger (int 0-59 or list)
  - trigger_days      : list of day names (e.g. ["monday", "wednesday"]) or
                        cron day-of-week values (0=Sun … 6=Sat)
  - timezone          : IANA timezone string (e.g. "America/New_York")
"""
from __future__ import annotations

import datetime
import structlog
import httpx  # noqa: F401 — standard import

from core.execution_engine import register_node
from oauth.flow import get_credential_data  # noqa: F401 — standard import

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# croniter — optional
# ---------------------------------------------------------------------------
try:
    from croniter import croniter  # type: ignore
    _CRON_BACKEND = "croniter"
except ImportError:
    croniter = None  # type: ignore
    _CRON_BACKEND = "manual"

# ---------------------------------------------------------------------------
# Day-name helpers
# ---------------------------------------------------------------------------

_DAY_MAP = {
    "sunday": 0, "sun": 0,
    "monday": 1, "mon": 1,
    "tuesday": 2, "tue": 2,
    "wednesday": 3, "wed": 3,
    "thursday": 4, "thu": 4,
    "friday": 5, "fri": 5,
    "saturday": 6, "sat": 6,
}


def _days_to_cron(trigger_days: list) -> str:
    """Convert a list of day names or numbers to a cron DOW field."""
    if not trigger_days:
        return "*"
    nums = []
    for d in trigger_days:
        if isinstance(d, int):
            nums.append(str(d))
        elif isinstance(d, str):
            key = d.lower().strip()
            if key.isdigit():
                nums.append(key)
            else:
                nums.append(str(_DAY_MAP.get(key, key)))
    return ",".join(nums) if nums else "*"


def _build_cron_expr(hour, minute, trigger_days: list) -> str:
    """Build a cron expression from parts."""
    hour_field = "*" if hour is None else str(hour) if not isinstance(hour, list) else ",".join(map(str, hour))
    minute_field = "0" if minute is None else str(minute) if not isinstance(minute, list) else ",".join(map(str, minute))
    dow_field = _days_to_cron(trigger_days)
    return f"{minute_field} {hour_field} * * {dow_field}"


def _next_run_manual(cron_expr: str, base: datetime.datetime) -> str:
    """Rough next-run estimate without croniter (next occurrence within 7 days)."""
    parts = cron_expr.split()
    if len(parts) < 5:
        return "unknown"
    try:
        minute_f, hour_f = parts[0], parts[1]
        hour = int(hour_f) if hour_f != "*" else base.hour
        minute = int(minute_f) if minute_f != "*" else base.minute
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            candidate += datetime.timedelta(days=1)
        return candidate.isoformat()
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@register_node("schedule.trigger")
async def trigger(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Evaluate schedule config and return scheduling metadata."""
    hour = config.get("trigger_at_hour", input_data.get("trigger_at_hour"))
    minute = config.get("trigger_at_minute", input_data.get("trigger_at_minute", 0))
    trigger_days = config.get("trigger_days", input_data.get("trigger_days", []))
    timezone = config.get("timezone", input_data.get("timezone", "UTC"))

    if isinstance(trigger_days, str):
        trigger_days = [d.strip() for d in trigger_days.split(",")]

    cron_expr = _build_cron_expr(hour, minute, trigger_days)

    # Current time
    triggered_at = datetime.datetime.utcnow().isoformat() + "Z"

    # Next run calculation
    if croniter is not None:
        try:
            base = datetime.datetime.utcnow()
            it = croniter(cron_expr, base)
            next_run = it.get_next(datetime.datetime).isoformat() + "Z"
        except Exception as exc:
            log.warning("schedule.trigger.croniter_error", error=str(exc))
            next_run = _next_run_manual(cron_expr, datetime.datetime.utcnow())
    else:
        next_run = _next_run_manual(cron_expr, datetime.datetime.utcnow())

    schedule_info = {
        "cron_expression": cron_expr,
        "trigger_at_hour": hour,
        "trigger_at_minute": minute,
        "trigger_days": trigger_days,
        "timezone": timezone,
        "backend": _CRON_BACKEND,
    }

    log.info("schedule.trigger", cron=cron_expr, timezone=timezone, next_run=next_run)
    return {
        "schedule_info": schedule_info,
        "next_run": next_run,
        "triggered_at": triggered_at,
    }
