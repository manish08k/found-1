"""Amazon SNS integration for pub/sub messaging."""
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
        "sns",
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        region_name=creds.get("region_name", "us-east-1"),
    )


@register_node("amazon_sns.publish")
async def sns_publish(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Publish a message to an SNS topic or directly to a phone number."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    message = merged.get("message", "")
    topic_arn = merged.get("topic_arn")
    target_arn = merged.get("target_arn")
    phone_number = merged.get("phone_number")
    if not message:
        raise ValueError("publish requires 'message'")
    if not any([topic_arn, target_arn, phone_number]):
        raise ValueError("publish requires at least one of: 'topic_arn', 'target_arn', 'phone_number'")

    def _publish():
        client = _get_client(creds)
        kwargs = {"Message": message}
        if topic_arn:
            kwargs["TopicArn"] = topic_arn
        elif target_arn:
            kwargs["TargetArn"] = target_arn
        elif phone_number:
            kwargs["PhoneNumber"] = phone_number
        subject = merged.get("subject")
        if subject:
            kwargs["Subject"] = subject
        msg_attrs = merged.get("message_attributes")
        if msg_attrs:
            kwargs["MessageAttributes"] = msg_attrs
        response = client.publish(**kwargs)
        return {"message_id": response.get("MessageId"), "sequence_number": response.get("SequenceNumber")}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _publish)


@register_node("amazon_sns.create_topic")
async def sns_create_topic(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an SNS topic."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    name = merged.get("name") or merged.get("topic_name")
    if not name:
        raise ValueError("create_topic requires 'name'")

    def _create():
        client = _get_client(creds)
        kwargs = {"Name": name}
        attrs = merged.get("attributes")
        if attrs:
            kwargs["Attributes"] = attrs
        response = client.create_topic(**kwargs)
        return {"topic_arn": response.get("TopicArn")}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create)


@register_node("amazon_sns.list_topics")
async def sns_list_topics(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all SNS topics in the account."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged

    def _list():
        client = _get_client(creds)
        topics = []
        paginator = client.get_paginator("list_topics")
        for page in paginator.paginate():
            topics.extend(page.get("Topics", []))
        return {"topics": topics, "count": len(topics)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list)


@register_node("amazon_sns.subscribe")
async def sns_subscribe(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Subscribe an endpoint to an SNS topic."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    topic_arn = merged.get("topic_arn")
    protocol = merged.get("protocol")  # email, sqs, lambda, http, sms, etc.
    endpoint = merged.get("endpoint")
    if not topic_arn or not protocol or not endpoint:
        raise ValueError("subscribe requires 'topic_arn', 'protocol', and 'endpoint'")

    def _subscribe():
        client = _get_client(creds)
        response = client.subscribe(TopicArn=topic_arn, Protocol=protocol, Endpoint=endpoint)
        return {"subscription_arn": response.get("SubscriptionArn")}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _subscribe)


@register_node("amazon_sns.unsubscribe")
async def sns_unsubscribe(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Unsubscribe from an SNS topic."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    subscription_arn = merged.get("subscription_arn")
    if not subscription_arn:
        raise ValueError("unsubscribe requires 'subscription_arn'")

    def _unsub():
        client = _get_client(creds)
        client.unsubscribe(SubscriptionArn=subscription_arn)
        return {"subscription_arn": subscription_arn, "status": "unsubscribed"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _unsub)
