"""Google Cloud Pub/Sub integration — message streaming."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("gcloud_pubsub.publish_message")
async def gcloud_pubsub_publish_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Publish a message to a Google Cloud Pub/Sub topic."""
    merged = {**config, **input_data}
    try:
        from google.cloud import pubsub_v1
        import base64
        project_id = merged.get("project_id", "")
        topic_id = merged.get("topic_id", "")
        message_data = merged.get("message", "")
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, topic_id)
        data = message_data.encode("utf-8") if isinstance(message_data, str) else str(message_data).encode("utf-8")
        future = publisher.publish(topic_path, data=data, **merged.get("attributes", {}))
        msg_id = future.result(timeout=30)
        return {"message_id": msg_id, "topic": topic_path}
    except ImportError:
        return {"error": "google-cloud-pubsub not installed", "status": "failed"}


@register_node("gcloud_pubsub.pull_messages")
async def gcloud_pubsub_pull_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    try:
        from google.cloud import pubsub_v1
        project_id = merged.get("project_id", "")
        subscription_id = merged.get("subscription_id", "")
        max_messages = merged.get("max_messages", 10)
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(project_id, subscription_id)
        response = subscriber.pull(request={"subscription": subscription_path, "max_messages": max_messages})
        messages = [{"data": m.message.data.decode("utf-8"), "message_id": m.message.message_id} for m in response.received_messages]
        if response.received_messages:
            ack_ids = [m.ack_id for m in response.received_messages]
            subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": ack_ids})
        return {"messages": messages, "count": len(messages)}
    except ImportError:
        return {"error": "google-cloud-pubsub not installed", "messages": []}
