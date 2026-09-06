"""Microsoft Copilot integration — send messages and list conversations via Teams/Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("microsoft_copilot.send_message")
async def microsoft_copilot_send_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a message to a Teams chat (used as Copilot conversation channel).

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      chat_id      — Teams chat ID to send the message to (required)
      content      — message body content (required)
      content_type — content type, "text" or "html" (optional, default "text")
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    chat_id = merged.get("chat_id")
    content = merged.get("content")
    if not chat_id:
        raise ValueError("chat_id is required for microsoft_copilot.send_message")
    if not content:
        raise ValueError("content is required for microsoft_copilot.send_message")

    payload = {
        "body": {
            "contentType": merged.get("content_type", "text"),
            "content": content,
        }
    }

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post(f"/me/chats/{chat_id}/messages", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        message = r.json()

    log.info("microsoft_copilot.send_message", chat_id=chat_id, message_id=message.get("id"))
    return {"message": message, "message_id": message.get("id"), "chat_id": chat_id}


@register_node("microsoft_copilot.list_conversations")
async def microsoft_copilot_list_conversations(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Teams chats (conversations) for the authenticated user.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      top          — maximum number of chats to return (optional, default 50)
      filter       — OData filter expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get("/me/chats", headers=_graph_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    chats = data.get("value", [])
    log.info("microsoft_copilot.list_conversations", count=len(chats))
    return {"conversations": chats, "count": len(chats)}
