"""Amazon SES integration for sending emails and managing identities."""
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
        "ses",
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        region_name=creds.get("region_name", "us-east-1"),
    )


@register_node("amazon_ses.send_email")
async def send_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a transactional email via Amazon SES."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    source = merged.get("source") or merged.get("from_email")
    to_addresses = merged.get("to_addresses") or merged.get("to")
    subject = merged.get("subject", "")
    if not source or not to_addresses or not subject:
        raise ValueError("send_email requires 'source', 'to_addresses', and 'subject'")
    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]

    html_body = merged.get("html_body") or merged.get("body_html", "")
    text_body = merged.get("text_body") or merged.get("body_text", "")

    def _send():
        client = _get_client(creds)
        body = {}
        if html_body:
            body["Html"] = {"Data": html_body, "Charset": "UTF-8"}
        if text_body:
            body["Text"] = {"Data": text_body, "Charset": "UTF-8"}
        if not body:
            body["Text"] = {"Data": "", "Charset": "UTF-8"}

        dest = {"ToAddresses": to_addresses}
        cc = merged.get("cc_addresses")
        bcc = merged.get("bcc_addresses")
        if cc:
            dest["CcAddresses"] = cc if isinstance(cc, list) else [cc]
        if bcc:
            dest["BccAddresses"] = bcc if isinstance(bcc, list) else [bcc]

        response = client.send_email(
            Source=source,
            Destination=dest,
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": body,
            },
        )
        return {"message_id": response.get("MessageId"), "status": "sent"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


@register_node("amazon_ses.send_bulk_email")
async def send_bulk_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send bulk templated emails via Amazon SES."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    source = merged.get("source") or merged.get("from_email")
    template = merged.get("template")
    destinations = merged.get("destinations", [])
    if not source or not template:
        raise ValueError("send_bulk_email requires 'source' and 'template'")

    def _send():
        client = _get_client(creds)
        bulk_destinations = []
        for dest in destinations:
            bulk_destinations.append({
                "Destination": {"ToAddresses": dest.get("to_addresses", [])},
                "ReplacementTemplateData": dest.get("template_data", "{}"),
            })
        response = client.send_bulk_templated_email(
            Source=source,
            Template=template,
            DefaultTemplateData=merged.get("default_template_data", "{}"),
            Destinations=bulk_destinations,
        )
        return {"status": response.get("Status", []), "count": len(bulk_destinations)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send)


@register_node("amazon_ses.list_identities")
async def list_identities(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List verified email addresses and domains in SES."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    identity_type = merged.get("identity_type", "EmailAddress")  # EmailAddress or Domain

    def _list():
        client = _get_client(creds)
        response = client.list_identities(IdentityType=identity_type, MaxItems=100)
        identities = response.get("Identities", [])
        return {"identities": identities, "count": len(identities)}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list)


@register_node("amazon_ses.verify_email")
async def verify_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Initiate verification of an email address in SES."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    email_address = merged.get("email_address") or merged.get("email")
    if not email_address:
        raise ValueError("verify_email requires 'email_address'")

    def _verify():
        client = _get_client(creds)
        client.verify_email_identity(EmailAddress=email_address)
        return {"email_address": email_address, "status": "verification_email_sent"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _verify)
