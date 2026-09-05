"""SSE Trigger integration — listen to Server-Sent Events endpoints."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _parse_sse_line(line: str, current_event: dict) -> dict | None:
    """Parse a single SSE line and update current_event state.

    Returns a complete event dict when a blank line is encountered, else None.
    """
    line = line.rstrip("\n").rstrip("\r")

    if line == "":
        # Empty line signals end of event — emit if we have data
        if current_event.get("data") is not None:
            event = {
                "event": current_event.get("data", ""),
                "id": current_event.get("id", ""),
                "type": current_event.get("event", "message"),
            }
            current_event.clear()
            return event
        return None

    if line.startswith(":"):
        # Comment line — ignore
        return None

    if ":" in line:
        field, _, value = line.partition(":")
        value = value.lstrip(" ")
    else:
        field = line
        value = ""

    current_event[field] = value
    return None


@register_node("sse_trigger.listen")
async def sse_listen(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Connect to an SSE endpoint and collect events.

    config/input_data:
      url        — SSE endpoint URL (required)
      token      — optional Bearer token for authentication
      max_events — maximum number of events to collect (default 1)
    """
    merged = {**config, **input_data}
    url = merged.get("url") or ""
    token = merged.get("token") or ""
    max_events = int(merged.get("max_events", 1))

    if not url:
        raise ValueError("url is required for sse_trigger.listen")

    headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    collected_events = []
    current_event: dict = {}

    async with httpx.AsyncClient(timeout=30) as client:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                event = _parse_sse_line(line, current_event)
                if event is not None:
                    collected_events.append(event)
                    if len(collected_events) >= max_events:
                        break

    log.info("sse_trigger.listen", url=url, events_collected=len(collected_events))

    if max_events == 1:
        single = collected_events[0] if collected_events else {"event": "", "id": "", "type": "message"}
        return {
            "event": single["event"],
            "id": single["id"],
            "type": single["type"],
        }

    return {
        "events": collected_events,
        "count": len(collected_events),
    }
