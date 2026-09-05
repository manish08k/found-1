"""
Apache Kafka message streaming integration.

Provides message production and consumption via the `aiokafka` library
when available, with a clear error message when it is not installed.

Credential fields:
  - bootstrap_servers : comma-separated list of broker host:port pairs
  - username          : SASL username (optional — enables SASL_PLAINTEXT)
  - password          : SASL password (optional)
  - sasl_mechanism    : SASL mechanism, e.g. 'PLAIN' or 'SCRAM-SHA-256'
                        (default 'PLAIN' when username is set)

Nodes:
  - kafka.produce : send a message to a Kafka topic
  - kafka.consume : poll messages from a Kafka topic
"""
import json
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency
# ---------------------------------------------------------------------------
try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer  # type: ignore
    _AIOKAFKA_AVAILABLE = True
except ImportError:
    _AIOKAFKA_AVAILABLE = False
    AIOKafkaProducer = None  # type: ignore
    AIOKafkaConsumer = None  # type: ignore

_NOT_INSTALLED_MSG = (
    "kafka integration requires 'aiokafka'. "
    "Install it: pip install aiokafka"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_creds(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    bootstrap = creds.get("bootstrap_servers", "").strip()
    if not bootstrap:
        raise ValueError("kafka credential missing 'bootstrap_servers'")
    return creds


def _build_producer_kwargs(creds: dict) -> dict:
    bootstrap = creds["bootstrap_servers"]
    kwargs: dict = {"bootstrap_servers": bootstrap}
    username = creds.get("username", "").strip()
    password = creds.get("password", "").strip()
    if username:
        mechanism = creds.get("sasl_mechanism", "PLAIN").upper()
        kwargs["security_protocol"] = "SASL_PLAINTEXT"
        kwargs["sasl_mechanism"] = mechanism
        kwargs["sasl_plain_username"] = username
        kwargs["sasl_plain_password"] = password
    return kwargs


def _build_consumer_kwargs(creds: dict, group_id: str, auto_offset: str) -> dict:
    kwargs = _build_producer_kwargs(creds)
    kwargs["group_id"] = group_id
    kwargs["auto_offset_reset"] = auto_offset
    kwargs["enable_auto_commit"] = True
    return kwargs


def _encode(value) -> bytes:
    """Encode a message value to bytes."""
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return json.dumps(value).encode("utf-8")


def _decode(raw: bytes | None) -> object:
    """Decode bytes from Kafka into a Python object."""
    if not raw:
        return None
    text = raw.decode("utf-8")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("kafka.produce")
async def kafka_produce(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Send a message to a Kafka topic.

    Config / input_data fields:
      - topic   (required) : target Kafka topic name
      - message (required) : message value (string, dict, or bytes)
      - key                : optional message key (string or bytes)
      - headers            : dict of additional message headers (optional)
      - partition          : target partition (int, optional)

    Credential fields:
      - bootstrap_servers : comma-separated broker addresses
      - username / password / sasl_mechanism : optional SASL auth
    """
    if not _AIOKAFKA_AVAILABLE:
        raise RuntimeError(_NOT_INSTALLED_MSG)

    topic = config.get("topic") or input_data.get("topic")
    message = config.get("message") if "message" in config else input_data.get("message")

    if not topic:
        raise ValueError("kafka.produce requires 'topic'")
    if message is None:
        raise ValueError("kafka.produce requires 'message'")

    key_raw = config.get("key") or input_data.get("key")
    headers_raw = config.get("headers") or input_data.get("headers", {})
    partition = config.get("partition") or input_data.get("partition")

    creds = await _get_creds(credential_id, db)
    producer_kwargs = _build_producer_kwargs(creds)

    key_bytes = _encode(key_raw) if key_raw is not None else None
    value_bytes = _encode(message)
    headers_list = list(headers_raw.items()) if headers_raw else []

    send_kwargs: dict = {"topic": topic, "value": value_bytes}
    if key_bytes is not None:
        send_kwargs["key"] = key_bytes
    if headers_list:
        send_kwargs["headers"] = headers_list
    if partition is not None:
        send_kwargs["partition"] = int(partition)

    log.info("kafka.produce", topic=topic, value_size=len(value_bytes))

    producer = AIOKafkaProducer(**producer_kwargs)
    await producer.start()
    try:
        record_meta = await producer.send_and_wait(**send_kwargs)
    finally:
        await producer.stop()

    return {
        "topic": record_meta.topic,
        "partition": record_meta.partition,
        "offset": record_meta.offset,
        "timestamp": record_meta.timestamp,
    }


@register_node("kafka.consume")
async def kafka_consume(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Poll messages from a Kafka topic.

    Config / input_data fields:
      - topic           (required) : Kafka topic to consume from
      - group_id                   : consumer group ID (default 'found-automation')
      - max_messages               : max messages to return per call (default 10)
      - timeout_ms                 : poll timeout in milliseconds (default 5000)
      - auto_offset_reset          : 'earliest' | 'latest' (default 'latest')

    Credential fields:
      - bootstrap_servers : comma-separated broker addresses
      - username / password / sasl_mechanism : optional SASL auth
    """
    if not _AIOKAFKA_AVAILABLE:
        raise RuntimeError(_NOT_INSTALLED_MSG)

    topic = config.get("topic") or input_data.get("topic")
    if not topic:
        raise ValueError("kafka.consume requires 'topic'")

    group_id = config.get("group_id") or input_data.get("group_id", "found-automation")
    max_messages = int(config.get("max_messages") or input_data.get("max_messages", 10))
    timeout_ms = int(config.get("timeout_ms") or input_data.get("timeout_ms", 5000))
    auto_offset = config.get("auto_offset_reset") or input_data.get("auto_offset_reset", "latest")

    creds = await _get_creds(credential_id, db)
    consumer_kwargs = _build_consumer_kwargs(creds, group_id, auto_offset)

    log.info("kafka.consume", topic=topic, group_id=group_id, max_messages=max_messages)

    consumer = AIOKafkaConsumer(topic, **consumer_kwargs)
    await consumer.start()
    messages = []
    try:
        batch = await consumer.getmany(timeout_ms=timeout_ms, max_records=max_messages)
        for _tp, records in batch.items():
            for record in records:
                messages.append({
                    "topic": record.topic,
                    "partition": record.partition,
                    "offset": record.offset,
                    "key": _decode(record.key),
                    "value": _decode(record.value),
                    "timestamp": record.timestamp,
                    "headers": {k: v.decode("utf-8", errors="replace") for k, v in record.headers},
                })
    finally:
        await consumer.stop()

    return {"messages": messages, "count": len(messages), "topic": topic, "group_id": group_id}
