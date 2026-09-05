"""
AMQP / RabbitMQ message queue integration.

Provides message publishing and consumption via the AMQP protocol
using aio-pika for async operation.

Credential fields:
  - host     : RabbitMQ host (default: localhost)
  - port     : AMQP port (default: 5672)
  - username : RabbitMQ username (default: guest)
  - password : RabbitMQ password (default: guest)
  - vhost    : Virtual host (default: /)

Dependency: aio-pika (optional – raises ImportError message if not installed).
"""
import json as _json
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

try:
    import aio_pika
except ImportError:
    aio_pika = None  # type: ignore[assignment]

log = structlog.get_logger(__name__)


def _require_aio_pika() -> None:
    if aio_pika is None:
        raise ImportError(
            "The 'aio-pika' package is required for AMQP integration but is not installed. "
            "Install it with: pip install aio-pika"
        )


async def _get_connection(credential_id: str, db):
    """Build an aio_pika connection from stored credentials."""
    _require_aio_pika()
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host", "localhost")
    port = int(creds.get("port", 5672))
    username = creds.get("username", "guest")
    password = creds.get("password", "guest")
    vhost = creds.get("vhost", "/")

    connection = await aio_pika.connect_robust(
        host=host,
        port=port,
        login=username,
        password=password,
        virtualhost=vhost,
        timeout=30,
    )
    return connection


@register_node("amqp.publish")
async def amqp_publish(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Publish a message to a RabbitMQ exchange or queue."""
    _require_aio_pika()

    exchange_name = config.get("exchange") or input_data.get("exchange", "")
    routing_key = config.get("routing_key") or input_data.get("routing_key", "")
    queue_name = config.get("queue") or input_data.get("queue", "")
    message_body = config.get("message") or input_data.get("message")
    content_type = config.get("content_type") or input_data.get("content_type", "application/json")
    durable = config.get("durable") if "durable" in config else input_data.get("durable", True)
    persistent = config.get("persistent") if "persistent" in config else input_data.get("persistent", True)

    # routing_key defaults to queue name for direct-to-queue publishing
    if not routing_key and queue_name:
        routing_key = queue_name

    if message_body is None:
        raise ValueError("amqp.publish requires 'message'")

    # Serialise non-string messages to JSON
    if isinstance(message_body, (dict, list)):
        body_bytes = _json.dumps(message_body).encode("utf-8")
        content_type = "application/json"
    else:
        body_bytes = str(message_body).encode("utf-8")

    delivery_mode = (
        aio_pika.DeliveryMode.PERSISTENT if persistent else aio_pika.DeliveryMode.NOT_PERSISTENT
    )

    connection = await _get_connection(credential_id, db)
    try:
        async with connection:
            channel = await connection.channel()

            # Ensure queue exists when targeting a queue directly
            if queue_name:
                await channel.declare_queue(queue_name, durable=bool(durable))

            # Resolve exchange object
            if exchange_name:
                exchange = await channel.get_exchange(exchange_name)
            else:
                exchange = channel.default_exchange

            amqp_message = aio_pika.Message(
                body=body_bytes,
                content_type=content_type,
                delivery_mode=delivery_mode,
            )
            await exchange.publish(amqp_message, routing_key=routing_key)

    finally:
        if not connection.is_closed:
            await connection.close()

    log.info("amqp.publish", exchange=exchange_name or "(default)", routing_key=routing_key)
    return {
        "published": True,
        "exchange": exchange_name or "(default)",
        "routing_key": routing_key,
        "content_type": content_type,
        "body_length": len(body_bytes),
    }


@register_node("amqp.consume")
async def amqp_consume(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Read one or more messages from a named RabbitMQ queue (non-blocking batch read)."""
    _require_aio_pika()

    queue_name = config.get("queue") or input_data.get("queue")
    if not queue_name:
        raise ValueError("amqp.consume requires 'queue'")

    max_messages = int(config.get("max_messages") or input_data.get("max_messages", 10))
    ack = config.get("ack") if "ack" in config else input_data.get("ack", True)
    durable = config.get("durable") if "durable" in config else input_data.get("durable", True)
    no_ack = not bool(ack)  # aio_pika terminology

    messages_out = []

    connection = await _get_connection(credential_id, db)
    try:
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=max_messages)
            queue = await channel.declare_queue(queue_name, durable=bool(durable), passive=True)

            for _ in range(max_messages):
                # get_message is non-blocking – returns None when queue is empty
                incoming = await queue.get(no_ack=no_ack, fail=False)
                if incoming is None:
                    break

                body = incoming.body
                try:
                    decoded = _json.loads(body)
                except Exception:
                    decoded = body.decode("utf-8", errors="replace")

                messages_out.append({
                    "body": decoded,
                    "routing_key": incoming.routing_key,
                    "exchange": incoming.exchange,
                    "delivery_tag": incoming.delivery_tag,
                    "content_type": incoming.content_type,
                })

                if bool(ack):
                    await incoming.ack()

    finally:
        if not connection.is_closed:
            await connection.close()

    log.info("amqp.consume", queue=queue_name, messages_received=len(messages_out))
    return {
        "messages": messages_out,
        "count": len(messages_out),
        "queue": queue_name,
    }
