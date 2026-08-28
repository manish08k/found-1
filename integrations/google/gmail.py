"""Gmail integration — send, read, label, search, polling."""
import base64
import email as email_lib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import structlog
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from core.execution_engine import register_node
from triggers.engine import register_poller
from credentials.encryption import decrypt_credential
from core.config import settings

log = structlog.get_logger(__name__)


async def _gmail_service(credential_id: str, db):
    from sqlalchemy import select
    from storage.models import OAuthCredential
    result = await db.execute(select(OAuthCredential).where(OAuthCredential.id == credential_id))
    cred_row = result.scalar_one()
    token_data = decrypt_credential(cred_row.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)

    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _build_raw_message(to: str, subject: str, body: str, html: bool = False,
                        cc: str = "", bcc: str = "", attachments: list = None) -> str:
    msg = MIMEMultipart("alternative" if html else "mixed")
    msg["to"] = to
    msg["subject"] = subject
    if cc:
        msg["cc"] = cc
    if bcc:
        msg["bcc"] = bcc

    if html:
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))

    if attachments:
        for att in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(base64.b64decode(att["data"]))
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{att["filename"]}"')
            msg.attach(part)

    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


@register_node("gmail.send_email")
async def gmail_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _gmail_service(credential_id, db)
    to = config.get("to") or input_data.get("to")
    subject = config.get("subject") or input_data.get("subject", "")
    body = config.get("body") or input_data.get("body", "")
    html = config.get("html", False)
    cc = config.get("cc") or input_data.get("cc", "")
    bcc = config.get("bcc") or input_data.get("bcc", "")
    attachments = config.get("attachments") or input_data.get("attachments")

    raw = _build_raw_message(to, subject, body, html, cc, bcc, attachments)
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"message_id": result["id"], "thread_id": result["threadId"]}


@register_node("gmail.get_emails")
async def gmail_get_emails(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _gmail_service(credential_id, db)
    query = config.get("query") or input_data.get("query", "is:unread")
    max_results = config.get("max_results", 10)
    label_ids = config.get("label_ids", ["INBOX"])

    list_result = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
        labelIds=label_ids,
    ).execute()

    messages = []
    for msg_ref in list_result.get("messages", []):
        msg = service.users().messages().get(
            userId="me",
            id=msg_ref["id"],
            format="full",
        ).execute()
        messages.append(_parse_message(msg))

    return {"emails": messages, "count": len(messages)}


@register_node("gmail.reply_email")
async def gmail_reply_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _gmail_service(credential_id, db)
    thread_id = config.get("thread_id") or input_data.get("thread_id")
    to = config.get("to") or input_data.get("to")
    subject = config.get("subject") or input_data.get("subject", "Re:")
    body = config.get("body") or input_data.get("body", "")

    raw = _build_raw_message(to, subject, body)
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": thread_id},
    ).execute()
    return {"message_id": result["id"], "thread_id": result["threadId"]}


@register_node("gmail.add_label")
async def gmail_add_label(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _gmail_service(credential_id, db)
    message_id = config.get("message_id") or input_data.get("message_id")
    label_ids = config.get("label_ids") or input_data.get("label_ids", [])

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": label_ids},
    ).execute()
    return {"ok": True, "message_id": message_id}


@register_node("gmail.mark_read")
async def gmail_mark_read(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _gmail_service(credential_id, db)
    message_id = config.get("message_id") or input_data.get("message_id")

    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()
    return {"ok": True}


@register_node("gmail.get_thread")
async def gmail_get_thread(config: dict, input_data: dict, credential_id: str, db) -> dict:
    service = await _gmail_service(credential_id, db)
    thread_id = config.get("thread_id") or input_data.get("thread_id")

    result = service.users().threads().get(userId="me", id=thread_id).execute()
    messages = [_parse_message(m) for m in result.get("messages", [])]
    return {"thread_id": thread_id, "messages": messages}


def _parse_message(msg: dict) -> dict:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = ""
    payload = msg.get("payload", {})

    if payload.get("body", {}).get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode(errors="replace")
    else:
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode(errors="replace")
                break

    return {
        "id": msg["id"],
        "thread_id": msg["threadId"],
        "from": headers.get("from"),
        "to": headers.get("to"),
        "subject": headers.get("subject"),
        "date": headers.get("date"),
        "snippet": msg.get("snippet"),
        "body": body,
        "labels": msg.get("labelIds", []),
    }


# ─── Polling: new unread email ────────────────────────────────────────────────

_gmail_seen: dict[str, set] = {}


@register_poller("gmail", "new_email")
async def poll_gmail_new_email(config: dict, credential_id: str, db) -> list[dict]:
    service = await _gmail_service(credential_id, db)
    query = config.get("query", "is:unread")
    key = f"{credential_id}:{query}"

    if key not in _gmail_seen:
        _gmail_seen[key] = set()

    try:
        list_result = service.users().messages().list(
            userId="me", q=query, maxResults=20
        ).execute()

        new_items = []
        for msg_ref in list_result.get("messages", []):
            if msg_ref["id"] not in _gmail_seen[key]:
                msg = service.users().messages().get(
                    userId="me", id=msg_ref["id"], format="full"
                ).execute()
                new_items.append(_parse_message(msg))
                _gmail_seen[key].add(msg_ref["id"])

        # Limit memory
        if len(_gmail_seen[key]) > 1000:
            _gmail_seen[key] = set(list(_gmail_seen[key])[-500:])

        return new_items
    except Exception as e:
        log.error("gmail_poll_error", error=str(e))
        return []
