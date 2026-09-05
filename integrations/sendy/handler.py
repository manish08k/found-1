"""
Sendy self-hosted email newsletter integration.

Credential fields:
  - api_key         : Sendy API key
  - installation_url: Base URL of your Sendy installation, e.g. https://sendy.example.com

Auth: api_key passed in form-encoded POST body.
Base URL: {installation_url}/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_creds(credential_id: str, db) -> tuple[str, str]:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    installation_url = creds.get("installation_url", "").rstrip("/")
    if not api_key:
        raise ValueError("Sendy credential missing 'api_key'")
    if not installation_url:
        raise ValueError("Sendy credential missing 'installation_url'")
    return api_key, installation_url


def _raise_for_status(r: httpx.Response, ok_values: tuple = ("1", "true")) -> str:
    text = r.text.strip()
    if r.status_code >= 300:
        raise ValueError(f"Sendy API HTTP error {r.status_code}: {text}")
    return text


@register_node("sendy.subscribe")
async def sendy_subscribe(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Subscribe an email address to a Sendy list."""
    api_key, base_url = await _get_creds(credential_id, db)
    email = config.get("email") or input_data.get("email")
    list_id = config.get("list_id") or input_data.get("list_id")
    name = config.get("name") or input_data.get("name", "")
    if not email:
        raise ValueError("sendy.subscribe requires 'email'")
    if not list_id:
        raise ValueError("sendy.subscribe requires 'list_id'")

    payload = {
        "api_key": api_key,
        "email": email,
        "list": list_id,
        "boolean": "true",
    }
    if name:
        payload["name"] = name

    log.info("sendy.subscribe", email=email, list_id=list_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{base_url}/subscribe", data=payload)
    text = _raise_for_status(r)
    success = text == "1"
    return {"success": success, "response": text, "email": email, "list_id": list_id}


@register_node("sendy.unsubscribe")
async def sendy_unsubscribe(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Unsubscribe an email address from a Sendy list."""
    api_key, base_url = await _get_creds(credential_id, db)
    email = config.get("email") or input_data.get("email")
    list_id = config.get("list_id") or input_data.get("list_id")
    if not email:
        raise ValueError("sendy.unsubscribe requires 'email'")
    if not list_id:
        raise ValueError("sendy.unsubscribe requires 'list_id'")

    payload = {
        "api_key": api_key,
        "email": email,
        "list": list_id,
        "boolean": "true",
    }

    log.info("sendy.unsubscribe", email=email, list_id=list_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{base_url}/unsubscribe", data=payload)
    text = _raise_for_status(r)
    success = text == "1"
    return {"success": success, "response": text, "email": email, "list_id": list_id}


@register_node("sendy.send_campaign")
async def sendy_send_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create and send a campaign via Sendy."""
    api_key, base_url = await _get_creds(credential_id, db)

    from_name = config.get("from_name") or input_data.get("from_name")
    from_email = config.get("from_email") or input_data.get("from_email")
    reply_to = config.get("reply_to") or input_data.get("reply_to", from_email)
    subject = config.get("subject") or input_data.get("subject")
    html_text = config.get("html_text") or input_data.get("html_text", "")
    plain_text = config.get("plain_text") or input_data.get("plain_text", "")
    list_ids = config.get("list_ids") or input_data.get("list_ids")
    brand_id = config.get("brand_id") or input_data.get("brand_id", "")

    for field, val in [("from_name", from_name), ("from_email", from_email), ("subject", subject)]:
        if not val:
            raise ValueError(f"sendy.send_campaign requires '{field}'")
    if not list_ids:
        raise ValueError("sendy.send_campaign requires 'list_ids'")

    # list_ids can be a list or comma-separated string
    if isinstance(list_ids, list):
        list_ids_str = ",".join(str(x) for x in list_ids)
    else:
        list_ids_str = str(list_ids)

    payload = {
        "api_key": api_key,
        "from_name": from_name,
        "from_email": from_email,
        "reply_to": reply_to,
        "subject": subject,
        "html_text": html_text,
        "plain_text": plain_text,
        "list_ids": list_ids_str,
        "send_campaign": "1",
    }
    if brand_id:
        payload["brand_id"] = brand_id

    log.info("sendy.send_campaign", subject=subject)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{base_url}/api/campaigns/create.php", data=payload)
    text = _raise_for_status(r)
    success = text == "Campaign created and now sending"
    return {"success": success, "response": text, "subject": subject}


@register_node("sendy.get_subscriber_count")
async def sendy_get_subscriber_count(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get the active subscriber count for a Sendy list."""
    api_key, base_url = await _get_creds(credential_id, db)
    list_id = config.get("list_id") or input_data.get("list_id")
    if not list_id:
        raise ValueError("sendy.get_subscriber_count requires 'list_id'")

    payload = {
        "api_key": api_key,
        "list_id": list_id,
    }

    log.info("sendy.get_subscriber_count", list_id=list_id)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{base_url}/api/subscribers/active-subscriber-count.php", data=payload)
    text = _raise_for_status(r)
    try:
        count = int(text)
    except ValueError:
        raise ValueError(f"Sendy get_subscriber_count error: {text}")
    return {"count": count, "list_id": list_id}
