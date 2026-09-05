"""
Citrix NetScaler ADC integration.

Auth: HTTP Basic (username + password) against a NetScaler host.
Uses the NetScaler NITRO REST API v1.

Credential fields:
  - host:     NetScaler management IP or hostname
  - username: NITRO username (e.g. nsroot)
  - password: NITRO password

Nodes:
  - netscaler.list_vservers      — list load-balancing virtual servers
  - netscaler.get_service_stats  — retrieve stats for a named service
  - netscaler.enable_service     — bring a service online
  - netscaler.disable_service    — take a service offline
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """Return (AsyncClient, base_url) configured for the NetScaler NITRO API."""
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host")
    username = creds.get("username")
    password = creds.get("password")
    if not host:
        raise ValueError("NetScaler credential missing 'host'")
    if not username:
        raise ValueError("NetScaler credential missing 'username'")
    if not password:
        raise ValueError("NetScaler credential missing 'password'")

    base_url = f"https://{host}/nitro/v1/config/"
    client = httpx.AsyncClient(
        base_url=base_url,
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
        verify=False,  # many appliances use self-signed certs
    )
    return client, base_url


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"NetScaler NITRO error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


@register_node("netscaler.list_vservers")
async def list_vservers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /nitro/v1/config/lbvserver — list all LB virtual servers.

    Config (optional):
      name — retrieve a specific virtual server by name
    """
    name = config.get("name") or input_data.get("name")
    path = f"lbvserver/{name}" if name else "lbvserver"
    log.info("netscaler.list_vservers", name=name)
    async with await _client(credential_id, db) as (client, _):
        r = await client.get(path)
    return _check(r)


@register_node("netscaler.get_service_stats")
async def get_service_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /nitro/v1/stat/service/{name} — retrieve stats for a named service.

    Config:
      name — (required) service name
    """
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("netscaler.get_service_stats requires 'name'")
    log.info("netscaler.get_service_stats", name=name)

    creds = await get_credential_data(credential_id, db)
    host = creds.get("host")
    username = creds.get("username")
    password = creds.get("password")
    if not host or not username or not password:
        raise ValueError("NetScaler credential missing 'host', 'username', or 'password'")

    async with httpx.AsyncClient(
        base_url=f"https://{host}/nitro/v1/stat/",
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
        verify=False,
    ) as client:
        r = await client.get(f"service/{name}")
    return _check(r)


@register_node("netscaler.enable_service")
async def enable_service(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /nitro/v1/config/service — enable a NetScaler service.

    Config:
      name — (required) service name
    """
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("netscaler.enable_service requires 'name'")
    log.info("netscaler.enable_service", name=name)
    payload = {"service": {"name": name}, "params": {"action": "enable"}}
    async with await _client(credential_id, db) as (client, _):
        r = await client.post("service?action=enable", json=payload)
    return _check(r)


@register_node("netscaler.disable_service")
async def disable_service(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /nitro/v1/config/service — disable a NetScaler service.

    Config:
      name  — (required) service name
      delay — (optional) graceful shutdown delay in seconds
    """
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("netscaler.disable_service requires 'name'")
    delay = config.get("delay") or input_data.get("delay")
    svc: dict = {"name": name}
    if delay is not None:
        svc["delay"] = int(delay)
    log.info("netscaler.disable_service", name=name, delay=delay)
    payload = {"service": svc}
    async with await _client(credential_id, db) as (client, _):
        r = await client.post("service?action=disable", json=payload)
    return _check(r)


async def test_connection(creds: dict) -> None:
    """Verify NetScaler credentials by listing LB virtual servers."""
    host = creds.get("host")
    username = creds.get("username")
    password = creds.get("password")
    if not host or not username or not password:
        raise ValueError("NetScaler requires 'host', 'username', and 'password'")
    async with httpx.AsyncClient(
        base_url=f"https://{host}/nitro/v1/config/",
        auth=(username, password),
        timeout=15.0,
        verify=False,
    ) as client:
        r = await client.get("lbvserver")
    if not r.is_success:
        raise ValueError(f"NetScaler connection failed: {r.status_code}")
