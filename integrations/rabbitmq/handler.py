"""
RabbitMQ message broker integration via Management HTTP API.

Credential fields:
  - host: RabbitMQ server hostname or IP
  - port: Management API port (default: 15672)
  - username: RabbitMQ username
  - password: RabbitMQ password
  - vhost: Virtual host (default: /)

Auth: HTTP Basic
Base URL: http://{host}:{port}/api
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host")
    if not host:
        raise ValueError("RabbitMQ credential is missing 'host'")
    port = creds.get("port") or 15672
    username = creds.get("username") or "guest"
    password = creds.get("password") or "guest"
    base_url = f"http://{host}:{port}/api"
    return httpx.AsyncClient(
        base_url=base_url,
        auth=(username, password),
        headers={"Content-Type": "application/json"},
        timeout=30.0,
    )


async def _get_vhost(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    return creds.get("vhost") or "/"


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"RabbitMQ API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"status": "ok", "text": r.text}


def _encode_vhost(vhost: str) -> str:
    """URL-encode the vhost for use in paths (/ -> %2F)."""
    import urllib.parse
    return urllib.parse.quote(vhost, safe="")


# ---------------------------------------------------------------------------
# Queues
# ---------------------------------------------------------------------------

@register_node("rabbitmq.list_queues")
async def rabbitmq_list_queues(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /queues — list all queues, optionally filtered by vhost."""
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    async with await _client(credential_id, db) as client:
        if vhost and vhost != "/":
            r = await client.get(f"/queues/{_encode_vhost(vhost)}")
        else:
            r = await client.get("/queues")
    return _check(r)


@register_node("rabbitmq.get_queue")
async def rabbitmq_get_queue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /queues/{vhost}/{name} — get details for a specific queue."""
    queue_name = config.get("name") or input_data.get("name")
    if not queue_name:
        raise ValueError("rabbitmq.get_queue requires 'name'")
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/queues/{_encode_vhost(vhost)}/{queue_name}")
    return _check(r)


@register_node("rabbitmq.create_queue")
async def rabbitmq_create_queue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /queues/{vhost}/{name} — create or declare a queue."""
    queue_name = config.get("name") or input_data.get("name")
    if not queue_name:
        raise ValueError("rabbitmq.create_queue requires 'name'")
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    body: dict = {}
    durable = config.get("durable")
    if durable is None:
        durable = input_data.get("durable")
    if durable is not None:
        body["durable"] = bool(durable)
    else:
        body["durable"] = True
    auto_delete = config.get("auto_delete")
    if auto_delete is None:
        auto_delete = input_data.get("auto_delete")
    if auto_delete is not None:
        body["auto_delete"] = bool(auto_delete)
    arguments = config.get("arguments") or input_data.get("arguments")
    if arguments:
        body["arguments"] = arguments
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/queues/{_encode_vhost(vhost)}/{queue_name}", json=body)
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"RabbitMQ API error {r.status_code}: {detail}")
    return {"created": True, "name": queue_name, "vhost": vhost}


@register_node("rabbitmq.delete_queue")
async def rabbitmq_delete_queue(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /queues/{vhost}/{name} — delete a queue."""
    queue_name = config.get("name") or input_data.get("name")
    if not queue_name:
        raise ValueError("rabbitmq.delete_queue requires 'name'")
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/queues/{_encode_vhost(vhost)}/{queue_name}")
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"RabbitMQ API error {r.status_code}: {detail}")
    return {"deleted": True, "name": queue_name}


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@register_node("rabbitmq.publish_message")
async def rabbitmq_publish_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /exchanges/{vhost}/{exchange}/publish — publish a message to an exchange."""
    exchange = config.get("exchange") or input_data.get("exchange") or ""
    routing_key = config.get("routing_key") or input_data.get("routing_key") or ""
    payload = config.get("payload") or input_data.get("payload") or ""
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    body = {
        "routing_key": routing_key,
        "payload": str(payload),
        "payload_encoding": config.get("payload_encoding") or input_data.get("payload_encoding") or "string",
        "properties": config.get("properties") or input_data.get("properties") or {},
    }
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/exchanges/{_encode_vhost(vhost)}/{exchange}/publish", json=body)
    return _check(r)


@register_node("rabbitmq.get_messages")
async def rabbitmq_get_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /queues/{vhost}/{name}/get — get (consume) messages from a queue."""
    queue_name = config.get("name") or input_data.get("name")
    if not queue_name:
        raise ValueError("rabbitmq.get_messages requires 'name'")
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    count = config.get("count") or input_data.get("count") or 1
    ackmode = config.get("ackmode") or input_data.get("ackmode") or "ack_requeue_true"
    body = {
        "count": int(count),
        "ackmode": ackmode,
        "encoding": config.get("encoding") or input_data.get("encoding") or "auto",
    }
    async with await _client(credential_id, db) as client:
        r = await client.post(f"/queues/{_encode_vhost(vhost)}/{queue_name}/get", json=body)
    return _check(r)


# ---------------------------------------------------------------------------
# Exchanges
# ---------------------------------------------------------------------------

@register_node("rabbitmq.list_exchanges")
async def rabbitmq_list_exchanges(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /exchanges — list all exchanges."""
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    async with await _client(credential_id, db) as client:
        if vhost and vhost != "/":
            r = await client.get(f"/exchanges/{_encode_vhost(vhost)}")
        else:
            r = await client.get("/exchanges")
    return _check(r)


@register_node("rabbitmq.create_exchange")
async def rabbitmq_create_exchange(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """PUT /exchanges/{vhost}/{name} — create or declare an exchange."""
    exchange_name = config.get("name") or input_data.get("name")
    if not exchange_name:
        raise ValueError("rabbitmq.create_exchange requires 'name'")
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    exchange_type = config.get("type") or input_data.get("type") or "direct"
    body: dict = {"type": exchange_type}
    durable = config.get("durable")
    if durable is None:
        durable = input_data.get("durable")
    body["durable"] = bool(durable) if durable is not None else True
    auto_delete = config.get("auto_delete")
    if auto_delete is None:
        auto_delete = input_data.get("auto_delete")
    if auto_delete is not None:
        body["auto_delete"] = bool(auto_delete)
    async with await _client(credential_id, db) as client:
        r = await client.put(f"/exchanges/{_encode_vhost(vhost)}/{exchange_name}", json=body)
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"RabbitMQ API error {r.status_code}: {detail}")
    return {"created": True, "name": exchange_name, "vhost": vhost, "type": exchange_type}


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------

@register_node("rabbitmq.list_bindings")
async def rabbitmq_list_bindings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /bindings — list all bindings."""
    vhost = config.get("vhost") or input_data.get("vhost") or await _get_vhost(credential_id, db)
    async with await _client(credential_id, db) as client:
        if vhost and vhost != "/":
            r = await client.get(f"/bindings/{_encode_vhost(vhost)}")
        else:
            r = await client.get("/bindings")
    return _check(r)


# ---------------------------------------------------------------------------
# Overview & Nodes
# ---------------------------------------------------------------------------

@register_node("rabbitmq.get_overview")
async def rabbitmq_get_overview(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /overview — get an overview of the RabbitMQ server."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/overview")
    return _check(r)


@register_node("rabbitmq.list_nodes")
async def rabbitmq_list_nodes(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /nodes — list all nodes in the cluster."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/nodes")
    return _check(r)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

async def test_connection(credential_id: str, db) -> dict:
    """Test RabbitMQ connection by fetching the server overview."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/overview")
    _check(r)
    data = r.json()
    return {"ok": True, "rabbitmq_version": data.get("rabbitmq_version", "unknown"),
            "node": data.get("node", "unknown")}
