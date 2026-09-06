"""Microsoft Outlook integration — email messages via Microsoft Graph API."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


@register_node("outlook.send_email")
async def outlook_send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an email via Microsoft Outlook.

    config/input_data:
      access_token  — Microsoft Graph OAuth2 bearer token (required)
      to            — list of recipient email addresses (required)
      subject       — email subject (required)
      body          — email body content (required)
      content_type  — body content type: "Text" or "HTML" (optional, default "Text")
      cc            — list of CC email addresses (optional)
      bcc           — list of BCC email addresses (optional)
      save_to_sent  — whether to save to Sent Items (optional, default True)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    to = merged.get("to", [])
    subject = merged.get("subject")
    body = merged.get("body")
    if not to:
        raise ValueError("to is required for outlook.send_email")
    if not subject:
        raise ValueError("subject is required for outlook.send_email")
    if body is None:
        raise ValueError("body is required for outlook.send_email")

    def _recipients(emails: list) -> list:
        return [{"emailAddress": {"address": e}} for e in emails]

    message: dict = {
        "subject": subject,
        "body": {"contentType": merged.get("content_type", "Text"), "content": body},
        "toRecipients": _recipients(to if isinstance(to, list) else [to]),
    }
    if merged.get("cc"):
        message["ccRecipients"] = _recipients(merged["cc"] if isinstance(merged["cc"], list) else [merged["cc"]])
    if merged.get("bcc"):
        message["bccRecipients"] = _recipients(merged["bcc"] if isinstance(merged["bcc"], list) else [merged["bcc"]])

    payload = {
        "message": message,
        "saveToSentItems": merged.get("save_to_sent", True),
    }

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post("/me/sendMail", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()

    log.info("outlook.send_email", subject=subject, to=to)
    return {"sent": True, "subject": subject, "to": to}


@register_node("outlook.list_messages")
async def outlook_list_messages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List email messages in the user's Outlook inbox.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      top          — maximum number of messages to return (optional, default 25)
      skip         — number of messages to skip for pagination (optional)
      filter       — OData filter expression (optional)
      folder       — mail folder name or ID, e.g. "inbox" (optional, default inbox)
      order_by     — OData orderby expression (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    folder = merged.get("folder", "inbox")

    params: dict = {}
    if merged.get("top"):
        params["$top"] = merged["top"]
    if merged.get("skip"):
        params["$skip"] = merged["skip"]
    if merged.get("filter"):
        params["$filter"] = merged["filter"]
    if merged.get("order_by"):
        params["$orderby"] = merged["order_by"]

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(
            f"/me/mailFolders/{folder}/messages",
            headers=_graph_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    messages = data.get("value", [])
    log.info("outlook.list_messages", folder=folder, count=len(messages))
    return {"messages": messages, "count": len(messages)}


@register_node("outlook.get_message")
async def outlook_get_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Outlook email message by ID.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      message_id   — message ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    message_id = merged.get("message_id")
    if not message_id:
        raise ValueError("message_id is required for outlook.get_message")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.get(f"/me/messages/{message_id}", headers=_graph_headers(access_token))
        r.raise_for_status()
        message = r.json()

    log.info("outlook.get_message", message_id=message_id, subject=message.get("subject"))
    return {"message": message, "message_id": message_id}


@register_node("outlook.delete_message")
async def outlook_delete_message(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete an Outlook email message.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      message_id   — message ID to delete (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    message_id = merged.get("message_id")
    if not message_id:
        raise ValueError("message_id is required for outlook.delete_message")

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.delete(f"/me/messages/{message_id}", headers=_graph_headers(access_token))
        r.raise_for_status()

    log.info("outlook.delete_message", message_id=message_id)
    return {"deleted": True, "message_id": message_id}


@register_node("outlook.create_draft")
async def outlook_create_draft(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a draft email in Microsoft Outlook.

    config/input_data:
      access_token — Microsoft Graph OAuth2 bearer token (required)
      to           — list of recipient email addresses (optional)
      subject      — email subject (optional)
      body         — email body content (optional)
      content_type — body content type: "Text" or "HTML" (optional, default "Text")
      cc           — list of CC email addresses (optional)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")

    def _recipients(emails: list) -> list:
        return [{"emailAddress": {"address": e}} for e in emails]

    payload: dict = {}
    if merged.get("subject"):
        payload["subject"] = merged["subject"]
    if merged.get("body") is not None:
        payload["body"] = {
            "contentType": merged.get("content_type", "Text"),
            "content": merged["body"],
        }
    if merged.get("to"):
        to = merged["to"]
        payload["toRecipients"] = _recipients(to if isinstance(to, list) else [to])
    if merged.get("cc"):
        cc = merged["cc"]
        payload["ccRecipients"] = _recipients(cc if isinstance(cc, list) else [cc])

    async with httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30) as client:
        r = await client.post("/me/messages", headers=_graph_headers(access_token), json=payload)
        r.raise_for_status()
        draft = r.json()

    log.info("outlook.create_draft", message_id=draft.get("id"), subject=draft.get("subject"))
    return {"draft": draft, "message_id": draft.get("id")}
