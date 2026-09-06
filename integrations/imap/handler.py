"""IMAP integration — read emails from IMAP server."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("imap.get_emails")
async def imap_get_emails(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch emails from IMAP server."""
    merged = {**config, **input_data}
    try:
        import imaplib, email
        host = merged.get("host", "imap.gmail.com")
        port = merged.get("port", 993)
        username = merged.get("username", "")
        password = merged.get("password", "")
        folder = merged.get("folder", "INBOX")
        limit = merged.get("limit", 10)
        with imaplib.IMAP4_SSL(host, port) as mail:
            mail.login(username, password)
            mail.select(folder)
            _, data = mail.search(None, merged.get("search", "UNSEEN"))
            ids = data[0].split()[-limit:]
            messages = []
            for uid in ids:
                _, msg_data = mail.fetch(uid, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                messages.append({
                    "id": uid.decode(), "subject": msg.get("Subject"),
                    "from": msg.get("From"), "date": msg.get("Date"),
                })
        return {"emails": messages, "count": len(messages)}
    except Exception as e:
        return {"error": str(e), "emails": []}


@register_node("imap.mark_as_read")
async def imap_mark_as_read(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    try:
        import imaplib
        host = merged.get("host", "imap.gmail.com")
        port = merged.get("port", 993)
        with imaplib.IMAP4_SSL(host, port) as mail:
            mail.login(merged.get("username", ""), merged.get("password", ""))
            mail.select(merged.get("folder", "INBOX"))
            mail.store(merged.get("message_id", "").encode(), "+FLAGS", r"\Seen")
        return {"ok": True}
    except Exception as e:
        return {"error": str(e), "ok": False}
