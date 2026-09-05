"""EmailSend integration — send emails via SMTP."""
import asyncio
import smtplib
import structlog
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _build_message(
    from_addr: str,
    to: list[str],
    subject: str,
    body: str,
    html: bool = False,
    attachments: list[dict] | None = None,
) -> MIMEMultipart:
    """Build a MIME email message."""
    msg = MIMEMultipart("alternative" if html else "mixed")
    msg["From"] = from_addr
    msg["To"] = ", ".join(to) if isinstance(to, list) else to
    msg["Subject"] = subject

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    for attachment in (attachments or []):
        # attachment: {filename, content (base64 or raw string), content_type}
        filename = attachment.get("filename", "attachment")
        content = attachment.get("content", "")
        mime_type = attachment.get("content_type", "application/octet-stream")

        main_type, sub_type = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")

        part = MIMEBase(main_type, sub_type)
        if isinstance(content, str):
            try:
                raw = base64.b64decode(content)
            except Exception:
                raw = content.encode("utf-8")
        else:
            raw = content

        part.set_payload(raw)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    return msg


@register_node("email_send.send")
async def email_send_send(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send an email via SMTP using stored credentials."""
    cred = await get_credential_data(credential_id, db)

    host = cred.get("host", "localhost")
    port = int(cred.get("port", 587))
    username = cred.get("username", "")
    password = cred.get("password", "")
    use_ssl = cred.get("use_ssl", False)
    if isinstance(use_ssl, str):
        use_ssl = use_ssl.lower() in ("true", "1", "yes")

    to = config.get("to") or input_data.get("to")
    from_addr = config.get("from_addr") or input_data.get("from_addr") or username
    subject = config.get("subject") or input_data.get("subject", "(no subject)")
    body = config.get("body") or input_data.get("body", "")
    html = config.get("html", False)
    attachments = config.get("attachments") or input_data.get("attachments", [])

    if isinstance(to, str):
        to = [addr.strip() for addr in to.split(",")]

    log.info("email_send.send", host=host, port=port, to=to, subject=subject)

    msg = _build_message(from_addr, to, subject, body, html=html, attachments=attachments)

    def _send_sync():
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port)
        else:
            server = smtplib.SMTP(host, port)

        try:
            server.ehlo()
            if not use_ssl:
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPException:
                    pass
            if username and password:
                server.login(username, password)
            server.sendmail(from_addr, to, msg.as_string())
        finally:
            server.quit()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_sync)

    log.info("email_send.send succeeded", to=to, subject=subject)
    return {"sent": True, "to": to, "subject": subject, "from": from_addr}
