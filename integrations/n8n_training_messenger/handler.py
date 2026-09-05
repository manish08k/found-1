"""
N8nTrainingCustomerMessenger integration.

A simulated messaging system intended for training demos and workflow examples.
No external HTTP calls or credentials required.

Messages are stored in a module-level list and persist for the lifetime of
the process. Each message is a dict with 'to', 'from', 'subject', 'body',
and 'timestamp' fields.
"""
import structlog
from datetime import datetime, timezone

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# Module-level in-memory message store
_MESSAGES: list[dict] = []


@register_node("n8n_training_messenger.send_message")
async def messenger_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Simulate sending a message by appending it to the in-memory store."""
    to = config.get("to") or input_data.get("to")
    body = config.get("body") or input_data.get("body") or config.get("message") or input_data.get("message")

    if not to:
        raise ValueError("n8n_training_messenger.send_message requires 'to'")
    if not body:
        raise ValueError("n8n_training_messenger.send_message requires 'body' or 'message'")

    from_ = config.get("from") or input_data.get("from", "system")
    subject = config.get("subject") or input_data.get("subject", "")

    message = {
        "id": len(_MESSAGES) + 1,
        "to": to,
        "from": from_,
        "subject": subject,
        "body": body,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _MESSAGES.append(message)

    log.info("n8n_training_messenger.send_message", to=to, message_id=message["id"])
    return {"message": message, "message_id": message["id"], "sent": True}


@register_node("n8n_training_messenger.list_messages")
async def messenger_list_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List messages, optionally filtered by recipient."""
    to_filter = config.get("to") or input_data.get("to")
    from_filter = config.get("from") or input_data.get("from")
    limit = int(config.get("limit") or input_data.get("limit", 50))

    messages = list(_MESSAGES)

    if to_filter:
        messages = [m for m in messages if m.get("to") == to_filter]
    if from_filter:
        messages = [m for m in messages if m.get("from") == from_filter]

    # Return most recent first
    messages = list(reversed(messages))[:limit]

    log.info("n8n_training_messenger.list_messages", to=to_filter, count=len(messages))
    return {"messages": messages, "count": len(messages)}


@register_node("n8n_training_messenger.clear_messages")
async def messenger_clear_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Clear all messages from the in-memory store."""
    count_before = len(_MESSAGES)
    _MESSAGES.clear()

    log.info("n8n_training_messenger.clear_messages", cleared=count_before)
    return {"cleared": count_before, "store_empty": True}
