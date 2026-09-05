"""
Cron schedule trigger integration.

Configuration-based trigger node — no credentials or HTTP calls required.
Validates a cron expression and returns schedule metadata.

Uses the `croniter` library if available for next-run calculation;
falls back to basic validation otherwise.
"""
import structlog
from datetime import datetime, timezone

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

try:
    from croniter import croniter, CroniterBadCronError
    _CRONITER_AVAILABLE = True
except ImportError:
    _CRONITER_AVAILABLE = False
    log.warning("croniter not installed; cron expression validation will be limited")


_COMMON_PRESETS = {
    "@yearly":   "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly":  "0 0 1 * *",
    "@weekly":   "0 0 * * 0",
    "@daily":    "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly":   "0 * * * *",
}

# Basic field range validation for cron expressions (without croniter)
_FIELD_RANGES = [
    (0, 59),   # minute
    (0, 23),   # hour
    (1, 31),   # day of month
    (1, 12),   # month
    (0, 7),    # day of week (0 and 7 both = Sunday)
]


def _resolve_preset(expr: str) -> str:
    """Expand @yearly etc. to 5-field expressions."""
    return _COMMON_PRESETS.get(expr.strip().lower(), expr)


def _basic_validate(expr: str) -> bool:
    """Perform minimal 5-field cron expression validation."""
    parts = expr.strip().split()
    if len(parts) != 5:
        return False
    for i, part in enumerate(parts):
        if part == "*":
            continue
        # Handle step expressions: */5
        if part.startswith("*/"):
            try:
                int(part[2:])
                continue
            except ValueError:
                return False
        # Handle range: 1-5
        if "-" in part:
            try:
                lo, hi = part.split("-", 1)
                lo_i, hi_i = int(lo), int(hi)
                min_v, max_v = _FIELD_RANGES[i]
                if lo_i < min_v or hi_i > max_v or lo_i > hi_i:
                    return False
                continue
            except ValueError:
                return False
        # Handle list: 1,2,3
        if "," in part:
            try:
                vals = [int(v) for v in part.split(",")]
                min_v, max_v = _FIELD_RANGES[i]
                if any(v < min_v or v > max_v for v in vals):
                    return False
                continue
            except ValueError:
                return False
        # Plain integer
        try:
            val = int(part)
            min_v, max_v = _FIELD_RANGES[i]
            if val < min_v or val > max_v:
                return False
        except ValueError:
            return False
    return True


@register_node("cron.trigger")
async def cron_trigger(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Validate a cron schedule and return schedule metadata.

    This is a trigger node: it represents a scheduled event and returns
    information about the schedule rather than performing an action.

    Config:
      - cron_expression : Standard 5-field cron expression, e.g. "0 * * * *"
                          or a preset like "@hourly", "@daily", "@weekly".
                          (required)
      - timezone        : IANA timezone string, e.g. "America/New_York" (default: "UTC")
      - description     : Optional human-readable description of the schedule

    Returns:
      - cron_expression   : Resolved 5-field cron expression
      - timezone          : Timezone used
      - is_valid          : Whether the expression is valid
      - next_runs         : List of next 5 scheduled run times (ISO format), if croniter available
      - description       : Human description (provided or auto-generated)
      - fields            : Parsed field breakdown (minute, hour, dom, month, dow)
    """
    raw_expr = config.get("cron_expression") or input_data.get("cron_expression")
    if not raw_expr:
        raise ValueError("cron.trigger requires 'cron_expression'")

    tz_name = config.get("timezone") or input_data.get("timezone", "UTC")
    description = config.get("description") or input_data.get("description", "")

    # Resolve presets
    cron_expr = _resolve_preset(str(raw_expr).strip())

    # Validate
    is_valid = False
    validation_error = None
    next_runs = []

    if _CRONITER_AVAILABLE:
        try:
            if not croniter.is_valid(cron_expr):
                raise CroniterBadCronError(f"Invalid cron expression: {cron_expr}")
            is_valid = True

            # Calculate next 5 run times
            now = datetime.now(timezone.utc)
            itr = croniter(cron_expr, now)
            for _ in range(5):
                next_dt = itr.get_next(datetime)
                next_runs.append(next_dt.isoformat())

        except CroniterBadCronError as e:
            is_valid = False
            validation_error = str(e)
    else:
        is_valid = _basic_validate(cron_expr)
        if not is_valid:
            validation_error = f"Invalid cron expression: '{cron_expr}'"

    if not is_valid:
        raise ValueError(validation_error or f"Invalid cron expression: '{cron_expr}'")

    # Parse fields for human-readable breakdown
    fields_raw = cron_expr.split()
    field_names = ["minute", "hour", "day_of_month", "month", "day_of_week"]
    fields = dict(zip(field_names, fields_raw))

    if not description:
        description = f"Runs on schedule: {cron_expr}"

    log.info("cron.trigger validated", cron_expression=cron_expr, timezone=tz_name)

    return {
        "cron_expression": cron_expr,
        "original_expression": raw_expr,
        "timezone": tz_name,
        "is_valid": is_valid,
        "next_runs": next_runs,
        "description": description,
        "fields": fields,
        "croniter_available": _CRONITER_AVAILABLE,
    }


@register_node("cron.validate_expression")
async def cron_validate_expression(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Validate a cron expression without raising on invalid input.

    Config:
      - cron_expression : The cron expression to validate (required)

    Returns:
      - is_valid          : Boolean
      - resolved_expression: The resolved expression (after preset expansion)
      - error             : Error message if invalid (null if valid)
      - next_run          : Next scheduled run time if valid and croniter is available
    """
    raw_expr = config.get("cron_expression") or input_data.get("cron_expression")
    if not raw_expr:
        raise ValueError("cron.validate_expression requires 'cron_expression'")

    cron_expr = _resolve_preset(str(raw_expr).strip())
    is_valid = False
    error = None
    next_run = None

    if _CRONITER_AVAILABLE:
        try:
            is_valid = croniter.is_valid(cron_expr)
            if not is_valid:
                error = f"Invalid cron expression: '{cron_expr}'"
            else:
                now = datetime.now(timezone.utc)
                itr = croniter(cron_expr, now)
                next_run = itr.get_next(datetime).isoformat()
        except Exception as e:
            is_valid = False
            error = str(e)
    else:
        is_valid = _basic_validate(cron_expr)
        if not is_valid:
            error = f"Invalid cron expression: '{cron_expr}'"

    return {
        "is_valid": is_valid,
        "resolved_expression": cron_expr,
        "original_expression": raw_expr,
        "error": error,
        "next_run": next_run,
    }
