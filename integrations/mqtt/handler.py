"""
MQTT IoT messaging integration.

Provides publish and subscribe capabilities for MQTT brokers.

Credential fields:
  - host     : MQTT broker hostname
  - port     : MQTT broker port (default 1883, or 8883 for SSL)
  - username : (optional) MQTT username
  - password : (optional) MQTT password
  - use_ssl  : (optional) boolean, use TLS/SSL connection

Requires: aiomqtt (preferred) or asyncio-mqtt
"""
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

try:
    import aiomqtt as _mqtt_lib
    _MQTT_BACKEND = "aiomqtt"
except ImportError:
    try:
        import asyncio_mqtt as _mqtt_lib  # type: ignore[no-redef]
        _MQTT_BACKEND = "asyncio_mqtt"
    except ImportError:
        _mqtt_lib = None  # type: ignore[assignment]
        _MQTT_BACKEND = None


async def _get_creds(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    host = creds.get("host")
    if not host:
        raise ValueError("MQTT credential missing 'host'")
    return creds


@register_node("mqtt.publish")
async def mqtt_publish(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Publish a message to an MQTT topic."""
    if _mqtt_lib is None:
        raise RuntimeError(
            "MQTT support requires 'aiomqtt' or 'asyncio-mqtt'. "
            "Install with: pip install aiomqtt"
        )

    topic = config.get("topic") or input_data.get("topic")
    payload = config.get("payload") or input_data.get("payload") or config.get("message") or input_data.get("message")

    if not topic:
        raise ValueError("mqtt.publish requires 'topic'")
    if payload is None:
        raise ValueError("mqtt.publish requires 'payload' or 'message'")

    creds = await _get_creds(credential_id, db)
    host = creds.get("host")
    port = int(creds.get("port", 1883))
    username = creds.get("username")
    password = creds.get("password")
    use_ssl = bool(creds.get("use_ssl", False))
    qos = int(config.get("qos") or input_data.get("qos", 0))
    retain = bool(config.get("retain") or input_data.get("retain", False))

    # Encode payload to bytes if needed
    if isinstance(payload, str):
        encoded_payload = payload.encode("utf-8")
    elif isinstance(payload, dict):
        import json
        encoded_payload = json.dumps(payload).encode("utf-8")
    else:
        encoded_payload = payload

    client_kwargs: dict = {
        "hostname": host,
        "port": port,
        "username": username,
        "password": password,
    }
    if use_ssl:
        import ssl
        client_kwargs["tls_context"] = ssl.create_default_context()

    log.info("mqtt.publish", host=host, port=port, topic=topic, qos=qos)

    async with _mqtt_lib.Client(**client_kwargs) as client:
        await client.publish(topic, payload=encoded_payload, qos=qos, retain=retain)

    return {
        "published": True,
        "topic": topic,
        "qos": qos,
        "retain": retain,
        "payload_size": len(encoded_payload),
    }


@register_node("mqtt.subscribe")
async def mqtt_subscribe(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Subscribe to an MQTT topic and collect messages for a short window."""
    if _mqtt_lib is None:
        raise RuntimeError(
            "MQTT support requires 'aiomqtt' or 'asyncio-mqtt'. "
            "Install with: pip install aiomqtt"
        )

    topic = config.get("topic") or input_data.get("topic")
    if not topic:
        raise ValueError("mqtt.subscribe requires 'topic'")

    timeout_seconds = float(config.get("timeout") or input_data.get("timeout", 5.0))
    max_messages = int(config.get("max_messages") or input_data.get("max_messages", 10))
    qos = int(config.get("qos") or input_data.get("qos", 0))

    creds = await _get_creds(credential_id, db)
    host = creds.get("host")
    port = int(creds.get("port", 1883))
    username = creds.get("username")
    password = creds.get("password")
    use_ssl = bool(creds.get("use_ssl", False))

    client_kwargs: dict = {
        "hostname": host,
        "port": port,
        "username": username,
        "password": password,
    }
    if use_ssl:
        import ssl
        client_kwargs["tls_context"] = ssl.create_default_context()

    log.info("mqtt.subscribe", host=host, port=port, topic=topic, timeout=timeout_seconds)

    import asyncio
    messages_collected: list = []

    async with _mqtt_lib.Client(**client_kwargs) as client:
        await client.subscribe(topic, qos=qos)
        try:
            async with asyncio.timeout(timeout_seconds):
                async for message in client.messages:
                    payload = message.payload
                    if isinstance(payload, (bytes, bytearray)):
                        try:
                            payload = payload.decode("utf-8")
                        except Exception:
                            payload = list(payload)
                    messages_collected.append({
                        "topic": str(message.topic),
                        "payload": payload,
                        "qos": message.qos,
                        "retain": message.retain,
                    })
                    if len(messages_collected) >= max_messages:
                        break
        except (asyncio.TimeoutError, TimeoutError):
            pass  # Timeout is expected — return what we have

    return {
        "messages": messages_collected,
        "count": len(messages_collected),
        "topic": topic,
    }
