"""
Onfleet last-mile delivery integration.

Auth: HTTP Basic where the username is the api_key and password is empty.

Credential fields:
  - api_key: Onfleet API key

Nodes:
  - onfleet.create_task       — create a delivery task
  - onfleet.get_task          — retrieve a task by ID
  - onfleet.list_workers      — list all workers / drivers
  - onfleet.create_recipient  — create a recipient (customer)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://onfleet.com/api/v2/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Onfleet credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        # Onfleet uses HTTP Basic: api_key as username, empty password
        auth=(api_key, ""),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Onfleet API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


@register_node("onfleet.create_task")
async def create_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /tasks — create a delivery task.

    Config:
      destination — (required) dict with address info:
                    {address: {unparsed: "123 Main St, City, ST 00000"}}
      recipients  — (required) list of recipient IDs or recipient objects
      notes       — task notes / instructions (optional)
      pickup_task — bool, this is a pickup (optional)
      complete_after  — Unix timestamp (optional)
      complete_before — Unix timestamp (optional)
      auto_assign     — dict for auto-assignment options (optional)
    """
    destination = config.get("destination") or input_data.get("destination")
    recipients = config.get("recipients") or input_data.get("recipients")
    if not destination:
        raise ValueError("onfleet.create_task requires 'destination'")
    if recipients is None:
        raise ValueError("onfleet.create_task requires 'recipients'")

    payload: dict = {"destination": destination, "recipients": recipients}
    for field in ("notes", "pickup_task", "complete_after", "complete_before", "auto_assign"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val

    log.info("onfleet.create_task")
    async with await _client(credential_id, db) as client:
        r = await client.post("tasks", json=payload)
    return _check(r)


@register_node("onfleet.get_task")
async def get_task(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /tasks/{id} — retrieve a task by its ID.

    Config:
      task_id — (required) Onfleet task ID
    """
    task_id = config.get("task_id") or input_data.get("task_id") or input_data.get("id")
    if not task_id:
        raise ValueError("onfleet.get_task requires 'task_id'")

    log.info("onfleet.get_task", task_id=task_id)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"tasks/{task_id}")
    return _check(r)


@register_node("onfleet.list_workers")
async def list_workers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /workers — list all workers.

    Config (all optional):
      filter      — comma-separated list of worker IDs
      teams       — comma-separated list of team IDs
      states      — comma-separated list of states (0=Unassigned,1=Idle,2=Active)
      analytics   — bool, include analytics (default: false)
    """
    params: dict = {}
    for field in ("filter", "teams", "states"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            params[field] = val
    analytics = config.get("analytics") if config.get("analytics") is not None else input_data.get("analytics")
    if analytics:
        params["analytics"] = "true"

    log.info("onfleet.list_workers", params=params)
    async with await _client(credential_id, db) as client:
        r = await client.get("workers", params=params)
    return _check(r)


@register_node("onfleet.create_recipient")
async def create_recipient(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /recipients — create a new recipient (customer).

    Config:
      name    — (required) recipient full name
      phone   — (required) E.164 phone number (e.g. +14155552671)
      notes   — notes about the recipient (optional)
      skip_sms_notifications — bool (optional)
    """
    name = config.get("name") or input_data.get("name")
    phone = config.get("phone") or input_data.get("phone")
    if not name:
        raise ValueError("onfleet.create_recipient requires 'name'")
    if not phone:
        raise ValueError("onfleet.create_recipient requires 'phone'")

    payload: dict = {"name": name, "phone": phone}
    for field in ("notes", "skip_sms_notifications"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val

    log.info("onfleet.create_recipient", name=name)
    async with await _client(credential_id, db) as client:
        r = await client.post("recipients", json=payload)
    return _check(r)


async def test_connection(creds: dict) -> None:
    """Verify Onfleet API key by fetching organization details."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Onfleet requires 'api_key'")
    async with httpx.AsyncClient(
        base_url=_BASE_URL, auth=(api_key, ""), timeout=15.0
    ) as client:
        r = await client.get("organization")
    if not r.is_success:
        raise ValueError(f"Onfleet connection failed: {r.status_code}")
