"""
iCalendar integration — generate and parse .ics files.

Uses the `icalendar` library when available; falls back to a minimal
stdlib-only implementation for .ics generation.

No credentials required.

Nodes:
  - icalendar.create_event   : build a VEVENT and return .ics content
  - icalendar.parse_ics      : parse .ics text and return a list of events
  - icalendar.list_events    : parse .ics and filter/list events
"""
import structlog
import uuid
import re
from datetime import datetime, timezone, timedelta

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------
try:
    import icalendar as _ical_lib  # type: ignore
    _ICAL_AVAILABLE = True
except ImportError:
    _ical_lib = None
    _ICAL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers — stdlib fallback
# ---------------------------------------------------------------------------

def _fmt_dt(dt_str: str) -> str:
    """Return an iCal-formatted datetime string (UTC)."""
    if not dt_str:
        return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Accept ISO 8601 variants
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y%m%dT%H%M%SZ")
        except ValueError:
            continue
    return dt_str  # pass through if already formatted


def _build_ics_stdlib(summary: str, dtstart: str, dtend: str, description: str,
                      location: str, uid: str, organizer: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FoundAutomation//iCalendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{_fmt_dt(dtstart)}",
        f"DTEND:{_fmt_dt(dtend)}",
        f"SUMMARY:{summary}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if location:
        lines.append(f"LOCATION:{location}")
    if organizer:
        lines.append(f"ORGANIZER:mailto:{organizer}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def _parse_ics_stdlib(ics_text: str) -> list[dict]:
    """Very basic parser for simple single/multi-event .ics files."""
    events: list[dict] = []
    current: dict | None = None
    for raw_line in ics_text.splitlines():
        line = raw_line.strip()
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, _, val = line.partition(":")
            current[key.upper()] = val
    return events


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("icalendar.create_event")
async def ical_create_event(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a VEVENT and return the .ics text.

    Config / input_data fields:
      - summary     (required) : event title
      - dtstart     : start datetime (ISO 8601 or YYYYMMDDTHHMMSSZ)
      - dtend       : end datetime (defaults to dtstart + 1 hour)
      - description : event description
      - location    : event location
      - organizer   : organiser email address
      - uid         : UID override (auto-generated if omitted)
    """
    summary = config.get("summary") or input_data.get("summary")
    if not summary:
        raise ValueError("icalendar.create_event requires 'summary'")

    dtstart = config.get("dtstart") or input_data.get("dtstart", "")
    dtend = config.get("dtend") or input_data.get("dtend", "")
    description = config.get("description") or input_data.get("description", "")
    location = config.get("location") or input_data.get("location", "")
    organizer = config.get("organizer") or input_data.get("organizer", "")
    uid = config.get("uid") or input_data.get("uid", str(uuid.uuid4()))

    # Default dtend = dtstart + 1 hour
    if dtstart and not dtend:
        fmt_start = _fmt_dt(dtstart)
        try:
            dt = datetime.strptime(fmt_start, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            dtend = (dt + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        except ValueError:
            dtend = dtstart

    if _ICAL_AVAILABLE:
        cal = _ical_lib.Calendar()
        cal.add("prodid", "-//FoundAutomation//iCalendar//EN")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("method", "PUBLISH")

        event = _ical_lib.Event()
        event.add("uid", uid)
        event.add("summary", summary)
        event.add("dtstamp", datetime.now(timezone.utc))

        def _parse_dt(s: str) -> datetime:
            fmt_s = _fmt_dt(s)
            return datetime.strptime(fmt_s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)

        if dtstart:
            event.add("dtstart", _parse_dt(dtstart))
        if dtend:
            event.add("dtend", _parse_dt(dtend) if dtend else None)
        if description:
            event.add("description", description)
        if location:
            event.add("location", location)
        if organizer:
            event.add("organizer", f"mailto:{organizer}")

        cal.add_component(event)
        ics_bytes = cal.to_ical()
        ics_text = ics_bytes.decode("utf-8")
    else:
        ics_text = _build_ics_stdlib(summary, dtstart, dtend, description, location, uid, organizer)

    log.info("icalendar.create_event", summary=summary, uid=uid)
    return {"ics": ics_text, "uid": uid, "summary": summary}


@register_node("icalendar.parse_ics")
async def ical_parse_ics(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Parse .ics text and return a structured list of events.

    Config / input_data fields:
      - ics (required) : raw .ics file content as a string
    """
    ics_text = config.get("ics") or input_data.get("ics")
    if not ics_text:
        raise ValueError("icalendar.parse_ics requires 'ics'")

    if _ICAL_AVAILABLE:
        cal = _ical_lib.Calendar.from_ical(ics_text)
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                ev: dict = {}
                for key in ("uid", "summary", "dtstart", "dtend", "dtstamp",
                            "description", "location", "organizer", "status"):
                    val = component.get(key)
                    if val is not None:
                        if hasattr(val, "dt"):
                            val = val.dt.isoformat() if hasattr(val.dt, "isoformat") else str(val.dt)
                        ev[key.upper()] = str(val)
                events.append(ev)
    else:
        events = _parse_ics_stdlib(ics_text)

    log.info("icalendar.parse_ics", event_count=len(events))
    return {"events": events, "count": len(events)}


@register_node("icalendar.list_events")
async def ical_list_events(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Parse .ics and optionally filter events by date range or keyword.

    Config / input_data fields:
      - ics            (required) : raw .ics content
      - filter_keyword            : substring to match against SUMMARY (case-insensitive)
      - after                     : ISO date; exclude events ending before this date
      - before                    : ISO date; exclude events starting after this date
      - limit                     : max number of events to return (default 100)
    """
    ics_text = config.get("ics") or input_data.get("ics")
    if not ics_text:
        raise ValueError("icalendar.list_events requires 'ics'")

    keyword = (config.get("filter_keyword") or input_data.get("filter_keyword", "")).lower()
    after_str = config.get("after") or input_data.get("after", "")
    before_str = config.get("before") or input_data.get("before", "")
    limit = int(config.get("limit") or input_data.get("limit", 100))

    # Re-use parse_ics logic
    parse_result = await ical_parse_ics(config, input_data, credential_id, db)
    all_events = parse_result["events"]

    filtered = []
    for ev in all_events:
        summary = ev.get("SUMMARY", "").lower()
        if keyword and keyword not in summary:
            continue
        filtered.append(ev)
        if len(filtered) >= limit:
            break

    log.info("icalendar.list_events", total=len(all_events), filtered=len(filtered))
    return {"events": filtered, "count": len(filtered), "total": len(all_events)}
