"""
Interval — schedule-based trigger that fires every N seconds/minutes/hours.

No credentials required.

Nodes:
  - interval.trigger : validate config and return schedule info
"""
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

_VALID_UNITS = {"seconds", "minutes", "hours"}

_UNIT_TO_SECONDS = {
    "seconds": 1,
    "minutes": 60,
    "hours": 3600,
}

_MIN_INTERVAL_SECONDS = 1
_MAX_INTERVAL_SECONDS = 7 * 24 * 3600  # 1 week


@register_node("interval.trigger")
async def interval_trigger(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Validate an interval configuration and return schedule metadata.

    Config / input_data fields:
      - value (required) : positive integer, the interval value
      - unit  (required) : one of 'seconds', 'minutes', 'hours'

    Returns schedule info including the total interval in seconds and a
    human-readable description.
    """
    value_raw = config.get("value") or input_data.get("value")
    unit = (config.get("unit") or input_data.get("unit", "")).lower().strip()

    if value_raw is None:
        raise ValueError("interval.trigger requires 'value'")
    if not unit:
        raise ValueError("interval.trigger requires 'unit'")

    try:
        value = int(value_raw)
    except (ValueError, TypeError):
        raise ValueError(f"interval.trigger: 'value' must be an integer, got: {value_raw!r}")

    if value <= 0:
        raise ValueError(f"interval.trigger: 'value' must be a positive integer, got: {value}")

    if unit not in _VALID_UNITS:
        raise ValueError(
            f"interval.trigger: 'unit' must be one of {sorted(_VALID_UNITS)}, got: {unit!r}"
        )

    interval_seconds = value * _UNIT_TO_SECONDS[unit]

    if interval_seconds < _MIN_INTERVAL_SECONDS:
        raise ValueError(
            f"interval.trigger: resulting interval ({interval_seconds}s) is below the minimum "
            f"of {_MIN_INTERVAL_SECONDS} second(s)"
        )

    if interval_seconds > _MAX_INTERVAL_SECONDS:
        raise ValueError(
            f"interval.trigger: resulting interval ({interval_seconds}s) exceeds the maximum "
            f"of {_MAX_INTERVAL_SECONDS} seconds (1 week)"
        )

    human = f"every {value} {unit}"
    cron_hint: str | None = None

    # Provide a cron expression hint for common cases
    if unit == "minutes" and 1 <= value <= 59:
        cron_hint = f"*/{value} * * * *"
    elif unit == "hours" and 1 <= value <= 23:
        cron_hint = f"0 */{value} * * *"
    elif unit == "seconds":
        cron_hint = None  # cron doesn't support sub-minute; hint is None

    log.info("interval.trigger", value=value, unit=unit, interval_seconds=interval_seconds)

    return {
        "value": value,
        "unit": unit,
        "interval_seconds": interval_seconds,
        "description": human,
        "cron_hint": cron_hint,
    }
