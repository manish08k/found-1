"""Amazon SQS integration for message queue operations."""
import json
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _get_client(creds: dict):
    if not HAS_BOTO3:
        raise ImportError("boto3 is required. Install with: pip install boto3")
    return boto3.client(
        "sqs",
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        region_name=creds.get("region_name", "us-east-1"),
    )


@register_node("amazon_sqs.send_message")
async def sqs_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to an SQS queue."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    queue_url = merged.get("queue_url")
    message_body = merged.get("message_body") or merged.get("message")
    if not queue_url or not message_body:
        raise ValueError("send_message requires 'queue_url' and 'message_body'")
    if isinstance(message_body, dict):
        message_body = json.dumps(message_body)

    def _send():
        client = _get_client(creds)
        kwargs = {"QueueUrl": queue_url, "MessageBody": message_body}
        delay = merged.get("delay_seconds")
        if delay is not None:
            kwargs["DelaySeconds"] = int(delay)
        attrs = merged.get("message_attributes")
        if attrs:
            kwargs["MessageAttributes"] = attrs
        dedup_id = merged.get("message_deduplication_id")
        if dedup_id:
            kwargs["MessageDeduplicationId"] = dedup_id
        group_id = merged.get("message_group_id")
        if group_id:
            kwargs["MessageGroupId"] = group_id
        response = client.send_message(**kwargs)
        return {
            "message_id": response.get("MessageId"),
            "md5_of_body": response.get("MD5OfMessageBody"),
            "sequence_number": response.get("SequenceNumber"),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


@register_node("amazon_sqs.receive_messages")
async def sqs_receive_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Receive messages from an SQS queue."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    queue_url = merged.get("queue_url")
    if not queue_url:
        raise ValueError("receive_messages requires 'queue_url'")
    max_messages = int(merged.get("max_number_of_messages", 10))
    wait_seconds = int(merged.get("wait_time_seconds", 0))
    visibility_timeout = merged.get("visibility_timeout")

    def _receive():
        client = _get_client(creds)
        kwargs = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": min(max_messages, 10),
            "WaitTimeSeconds": wait_seconds,
            "AttributeNames": ["All"],
            "MessageAttributeNames": ["All"],
        }
        if visibility_timeout is not None:
            kwargs["VisibilityTimeout"] = int(visibility_timeout)
        response = client.receive_message(**kwargs)
        messages = response.get("Messages", [])
        return {"messages": messages, "count": len(messages)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _receive)


@register_node("amazon_sqs.delete_message")
async def sqs_delete_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a message from an SQS queue after processing."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    queue_url = merged.get("queue_url")
    receipt_handle = merged.get("receipt_handle")
    if not queue_url or not receipt_handle:
        raise ValueError("delete_message requires 'queue_url' and 'receipt_handle'")

    def _delete():
        client = _get_client(creds)
        client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
        return {"status": "deleted", "receipt_handle": receipt_handle}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _delete)


@register_node("amazon_sqs.create_queue")
async def sqs_create_queue(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an SQS queue."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    queue_name = merged.get("queue_name") or merged.get("name")
    if not queue_name:
        raise ValueError("create_queue requires 'queue_name'")

    def _create():
        client = _get_client(creds)
        attrs = {}
        if merged.get("fifo"):
            attrs["FifoQueue"] = "true"
        if merged.get("visibility_timeout"):
            attrs["VisibilityTimeout"] = str(merged["visibility_timeout"])
        if merged.get("message_retention_period"):
            attrs["MessageRetentionPeriod"] = str(merged["message_retention_period"])
        kwargs = {"QueueName": queue_name}
        if attrs:
            kwargs["Attributes"] = attrs
        response = client.create_queue(**kwargs)
        return {"queue_url": response.get("QueueUrl")}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create)


@register_node("amazon_sqs.list_queues")
async def sqs_list_queues(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List SQS queues in the account."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    prefix = merged.get("queue_name_prefix")

    def _list():
        client = _get_client(creds)
        kwargs = {"MaxResults": 1000}
        if prefix:
            kwargs["QueueNamePrefix"] = prefix
        response = client.list_queues(**kwargs)
        queues = response.get("QueueUrls", [])
        return {"queue_urls": queues, "count": len(queues)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list)
