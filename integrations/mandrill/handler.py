"""
Mandrill transactional email integration.

Provides email sending, template management, and message info retrieval
via the Mandrill API v1.0.

Credential fields:
  - api_key : Mandrill API key (passed in JSON request body)

Auth: api_key field in JSON body.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://mandrillapp.com/api/1.0"


async def _get_api_key(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Mandrill credential missing 'api_key'")
    return api_key


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mandrill API error {r.status_code}: {detail}")


@register_node("mandrill.send_email")
async def mandrill_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send a transactional email via Mandrill."""
    api_key = await _get_api_key(credential_id, db)

    to_email = config.get("to_email") or input_data.get("to_email")
    to_name = config.get("to_name") or input_data.get("to_name", "")
    subject = config.get("subject") or input_data.get("subject")
    html = config.get("html") or input_data.get("html", "")
    text = config.get("text") or input_data.get("text", "")
    from_email = config.get("from_email") or input_data.get("from_email", "noreply@example.com")
    from_name = config.get("from_name") or input_data.get("from_name", "")

    if not to_email:
        raise ValueError("mandrill.send_email requires 'to_email'")
    if not subject:
        raise ValueError("mandrill.send_email requires 'subject'")

    payload = {
        "key": api_key,
        "message": {
            "html": html,
            "text": text,
            "subject": subject,
            "from_email": from_email,
            "from_name": from_name,
            "to": [{"email": to_email, "name": to_name, "type": "to"}],
        },
    }

    log.info("mandrill.send_email", to=to_email, subject=subject)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.post("/messages/send.json", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"result": data}


@register_node("mandrill.list_templates")
async def mandrill_list_templates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all Mandrill templates."""
    api_key = await _get_api_key(credential_id, db)
    label = config.get("label") or input_data.get("label", "")

    payload: dict = {"key": api_key}
    if label:
        payload["label"] = label

    log.info("mandrill.list_templates")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.post("/templates/list.json", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"templates": data}


@register_node("mandrill.send_template")
async def mandrill_send_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Send an email using a stored Mandrill template."""
    api_key = await _get_api_key(credential_id, db)

    template_name = config.get("template_name") or input_data.get("template_name")
    to_email = config.get("to_email") or input_data.get("to_email")
    to_name = config.get("to_name") or input_data.get("to_name", "")
    subject = config.get("subject") or input_data.get("subject", "")
    from_email = config.get("from_email") or input_data.get("from_email", "noreply@example.com")
    from_name = config.get("from_name") or input_data.get("from_name", "")
    merge_vars = config.get("merge_vars") or input_data.get("merge_vars", {})

    if not template_name:
        raise ValueError("mandrill.send_template requires 'template_name'")
    if not to_email:
        raise ValueError("mandrill.send_template requires 'to_email'")

    # Build per-recipient merge vars list from dict
    recipient_merge_vars = []
    if merge_vars and isinstance(merge_vars, dict):
        vars_list = [{"name": k, "content": v} for k, v in merge_vars.items()]
        recipient_merge_vars = [{"rcpt": to_email, "vars": vars_list}]

    payload = {
        "key": api_key,
        "template_name": template_name,
        "template_content": [],
        "message": {
            "subject": subject,
            "from_email": from_email,
            "from_name": from_name,
            "to": [{"email": to_email, "name": to_name, "type": "to"}],
            "merge_vars": recipient_merge_vars,
        },
    }

    log.info("mandrill.send_template", template=template_name, to=to_email)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.post("/messages/send-template.json", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"result": data}


@register_node("mandrill.get_message_info")
async def mandrill_get_message_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get info for a sent Mandrill message by ID."""
    api_key = await _get_api_key(credential_id, db)

    message_id = config.get("message_id") or input_data.get("message_id")
    if not message_id:
        raise ValueError("mandrill.get_message_info requires 'message_id'")

    payload = {"key": api_key, "id": message_id}

    log.info("mandrill.get_message_info", message_id=message_id)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.post("/messages/info.json", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"message": data}
