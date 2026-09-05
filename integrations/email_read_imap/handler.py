"""
EmailReadImap integration — read and manage emails via IMAP.

Uses Python's stdlib `imaplib` (no external HTTP dependencies).

Credential fields:
  - host     (str)  : IMAP server hostname, e.g. imap.gmail.com
  - port     (int)  : IMAP port. Default 993 (SSL) or 143 (plain).
  - username (str)  : Email / IMAP username.
  - password (str)  : Password or app-specific password.
  - ssl      (bool) : Use SSL. Default True.
"""
import email
import imaplib
import structlog
import httpx  # noqa: F401 – kept for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    required = ("host", "username", "password")
    for field in required:
        if not creds.get(field):
            raise ValueError(f"EmailReadImap credential missing '{field}'")
    return creds


def _connect(creds: dict) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
    host = creds["host"]
    port = int(creds.get("port", 993))
    use_ssl = str(creds.get("ssl", "true")).lower() not in ("false", "0", "no")

    if use_ssl:
        conn = imaplib.IMAP4_SSL(host, port)
    else:
        conn = imaplib.IMAP4(host, port)

    conn.login(creds["username"], creds["password"])
    return conn


def _decode_header_value(raw: str | bytes | None) -> str:
    """Decode an RFC-2047 encoded email header value."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        raw = raw.decode(errors="replace")
    parts = email.header.decode_header(raw)
    decoded_parts = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def _parse_message(raw_bytes: bytes) -> dict:
    """Parse a raw email message into a structured dict."""
    msg = email.message_from_bytes(raw_bytes)

    body_plain = ""
    body_html = ""
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp:
                attachments.append({
                    "filename": part.get_filename("unknown"),
                    "content_type": ctype,
                    "size": len(part.get_payload(decode=True) or b""),
                })
            elif ctype == "text/plain" and not body_plain:
                payload = part.get_payload(decode=True)
                body_plain = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            elif ctype == "text/html" and not body_html:
                payload = part.get_payload(decode=True)
                body_html = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body_plain = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

    return {
        "message_id": _decode_header_value(msg.get("Message-ID")),
        "subject": _decode_header_value(msg.get("Subject")),
        "from": _decode_header_value(msg.get("From")),
        "to": _decode_header_value(msg.get("To")),
        "cc": _decode_header_value(msg.get("Cc")),
        "date": _decode_header_value(msg.get("Date")),
        "body_plain": body_plain,
        "body_html": body_html,
        "attachments": attachments,
        "has_attachments": bool(attachments),
    }


@register_node("email_read_imap.get_messages")
async def get_messages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Fetch messages from an IMAP mailbox.

    Config / input keys:
      - mailbox    (str)  : Mailbox to read. Default "INBOX".
      - limit      (int)  : Max messages to return (newest first). Default 10.
      - unread_only (bool): Only return unseen messages. Default False.
      - search     (str)  : IMAP search criterion, e.g. 'FROM "user@example.com"'.
                            Overrides unread_only if set.
      - include_body (bool): Parse and return message bodies. Default True.

    Returns:
      { "messages": [...], "total_fetched": int, "mailbox": str }
    """
    mailbox = config.get("mailbox") or input_data.get("mailbox", "INBOX")
    limit = min(int(config.get("limit") or input_data.get("limit", 10)), 200)
    unread_only = str(config.get("unread_only") or input_data.get("unread_only", "false")).lower() in ("true", "1", "yes")
    custom_search = config.get("search") or input_data.get("search")
    include_body = str(config.get("include_body") or input_data.get("include_body", "true")).lower() not in ("false", "0", "no")

    creds = await _get_creds(credential_id, db)
    log.info("email_read_imap.get_messages", mailbox=mailbox, limit=limit)

    conn = _connect(creds)
    try:
        conn.select(mailbox, readonly=True)

        if custom_search:
            criterion = custom_search
        elif unread_only:
            criterion = "UNSEEN"
        else:
            criterion = "ALL"

        status, data = conn.search(None, criterion)
        if status != "OK":
            raise ValueError(f"IMAP search failed: {status}")

        message_ids = data[0].split()
        # Newest first: reverse and take limit
        message_ids = message_ids[::-1][:limit]

        messages = []
        for uid in message_ids:
            if include_body:
                fetch_status, msg_data = conn.fetch(uid, "(RFC822)")
                if fetch_status != "OK" or not msg_data or msg_data[0] is None:
                    continue
                raw = msg_data[0][1]
                parsed = _parse_message(raw)
                parsed["uid"] = uid.decode()
                messages.append(parsed)
            else:
                fetch_status, msg_data = conn.fetch(uid, "(BODY[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])")
                if fetch_status != "OK" or not msg_data or msg_data[0] is None:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                messages.append({
                    "uid": uid.decode(),
                    "message_id": _decode_header_value(msg.get("Message-ID")),
                    "subject": _decode_header_value(msg.get("Subject")),
                    "from": _decode_header_value(msg.get("From")),
                    "to": _decode_header_value(msg.get("To")),
                    "date": _decode_header_value(msg.get("Date")),
                })
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return {
        "messages": messages,
        "total_fetched": len(messages),
        "mailbox": mailbox,
        "criterion": criterion,
    }


@register_node("email_read_imap.mark_as_read")
async def mark_as_read(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Mark one or more messages as read (\\Seen flag).

    Config / input keys:
      - uid     (str|list) : Message UID(s) to mark as read.
      - mailbox (str)      : Mailbox containing the messages. Default "INBOX".

    Returns:
      { "marked": int, "uids": [...], "mailbox": str }
    """
    mailbox = config.get("mailbox") or input_data.get("mailbox", "INBOX")
    uid_raw = config.get("uid") or input_data.get("uid")

    if not uid_raw:
        raise ValueError("email_read_imap.mark_as_read requires 'uid'")

    uids = uid_raw if isinstance(uid_raw, list) else [str(uid_raw)]
    uid_set = ",".join(str(u) for u in uids)

    creds = await _get_creds(credential_id, db)
    log.info("email_read_imap.mark_as_read", mailbox=mailbox, uids=uids)

    conn = _connect(creds)
    try:
        conn.select(mailbox, readonly=False)
        status, _ = conn.store(uid_set, "+FLAGS", "\\Seen")
        if status != "OK":
            raise ValueError(f"IMAP STORE failed: {status}")
        conn.expunge()
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return {
        "marked": len(uids),
        "uids": uids,
        "mailbox": mailbox,
        "flag": "\\Seen",
    }


@register_node("email_read_imap.move_message")
async def move_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Move a message from one mailbox to another.

    IMAP does not have a native MOVE command in all implementations; this
    copies the message to the destination then deletes the original.

    Config / input keys:
      - uid             (str)  : Message UID to move.
      - source_mailbox  (str)  : Source mailbox. Default "INBOX".
      - target_mailbox  (str)  : Destination mailbox (must already exist).

    Returns:
      { "moved": bool, "uid": str, "from": str, "to": str }
    """
    uid = str(config.get("uid") or input_data.get("uid", ""))
    source = config.get("source_mailbox") or input_data.get("source_mailbox", "INBOX")
    target = config.get("target_mailbox") or input_data.get("target_mailbox")

    if not uid:
        raise ValueError("email_read_imap.move_message requires 'uid'")
    if not target:
        raise ValueError("email_read_imap.move_message requires 'target_mailbox'")

    creds = await _get_creds(credential_id, db)
    log.info("email_read_imap.move_message", uid=uid, source=source, target=target)

    conn = _connect(creds)
    try:
        conn.select(source, readonly=False)

        # Try server-side MOVE (RFC 6851) first
        if b"MOVE" in (conn.capabilities or b""):
            status, _ = conn.uid("MOVE", uid, target)
            if status != "OK":
                raise ValueError(f"IMAP MOVE failed: {status}")
        else:
            # Fallback: COPY then delete
            copy_status, _ = conn.copy(uid, target)
            if copy_status != "OK":
                raise ValueError(f"IMAP COPY failed: {copy_status}")
            conn.store(uid, "+FLAGS", "\\Deleted")
            conn.expunge()
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return {
        "moved": True,
        "uid": uid,
        "from": source,
        "to": target,
    }
