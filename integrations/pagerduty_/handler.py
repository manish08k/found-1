"""
PagerDuty integration — trigger and resolve incidents via the Events API
v2. Credential fields: {"routing_key": "..."} (an Events API integration
key from a PagerDuty service, not your account API key — routing keys
are scoped to trigger events on one service, which is the right blast
radius for a workflow node).
"""
import uuid
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

PAGERDUTY_EVENTS_BASE = "https://events.pagerduty.com/v2"


async def _routing_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    routing_key = creds.get("routing_key")
    if not routing_key:
        raise ValueError("PagerDuty credential is missing 'routing_key'")
    return routing_key


@register_node("pagerduty.trigger_incident")
async def pagerduty_trigger_incident(config: dict, input_data: dict, credential_id: str, db) -> dict:
    summary = config.get("summary") or input_data.get("summary")
    source = config.get("source", "autoflow")
    severity = config.get("severity", "error")
    if severity not in ("critical", "error", "warning", "info"):
        raise ValueError("pagerduty.trigger_incident: severity must be critical/error/warning/info")
    if not summary:
        raise ValueError("pagerduty.trigger_incident requires 'summary'")

    routing_key = await _routing_key(credential_id, db)
    dedup_key = config.get("dedup_key") or str(uuid.uuid4())

    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": dedup_key,
        "payload": {"summary": summary, "source": source, "severity": severity},
    }

    async with httpx.AsyncClient(base_url=PAGERDUTY_EVENTS_BASE, timeout=30) as client:
        r = await client.post("/enqueue", json=payload)
        r.raise_for_status()
        data = r.json()

    return {"status": data.get("status"), "dedup_key": data.get("dedup_key", dedup_key)}


@register_node("pagerduty.resolve_incident")
async def pagerduty_resolve_incident(config: dict, input_data: dict, credential_id: str, db) -> dict:
    dedup_key = config.get("dedup_key") or input_data.get("dedup_key")
    if not dedup_key:
        raise ValueError("pagerduty.resolve_incident requires 'dedup_key' (the one returned by trigger_incident)")

    routing_key = await _routing_key(credential_id, db)
    payload = {"routing_key": routing_key, "event_action": "resolve", "dedup_key": dedup_key}

    async with httpx.AsyncClient(base_url=PAGERDUTY_EVENTS_BASE, timeout=30) as client:
        r = await client.post("/enqueue", json=payload)
        r.raise_for_status()
        data = r.json()

    return {"status": data.get("status")}


async def test_connection(creds: dict) -> None:
    """
    PagerDuty's Events API has no lightweight "am I authenticated" probe
    — the only way to validate a routing key is to send a real event.
    Sending a trigger+immediate-resolve pair (rather than just a trigger)
    means the test doesn't leave a phantom open incident behind.
    """
    routing_key = creds.get("routing_key")
    if not routing_key:
        raise ValueError("Missing routing_key")
    dedup_key = f"autoflow-credential-test-{uuid.uuid4()}"
    async with httpx.AsyncClient(base_url=PAGERDUTY_EVENTS_BASE, timeout=10) as client:
        r = await client.post("/enqueue", json={
            "routing_key": routing_key, "event_action": "trigger", "dedup_key": dedup_key,
            "payload": {"summary": "AutoFlow credential test (auto-resolved)", "source": "autoflow", "severity": "info"},
        })
        r.raise_for_status()
        r2 = await client.post("/enqueue", json={"routing_key": routing_key, "event_action": "resolve", "dedup_key": dedup_key})
        r2.raise_for_status()
