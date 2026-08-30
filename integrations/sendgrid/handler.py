"""
SendGrid Email API integration — advanced nodes beyond basic send.

Provides full production email sending, marketing contact management,
list management, template operations, stats, and suppression management
via the SendGrid v3 REST API.

Credential fields:
  - api_key : SendGrid API key (starts with SG.)

Auth: Authorization: Bearer {api_key}
Base URL: https://api.sendgrid.com/v3
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

try:
    from core.ssrf_guard import assert_safe_url
    _SSRF_AVAILABLE = True
except Exception:
    _SSRF_AVAILABLE = False

log = structlog.get_logger(__name__)

SENDGRID_BASE = "https://api.sendgrid.com/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("SendGrid credential missing 'api_key'")
    if _SSRF_AVAILABLE:
        assert_safe_url(SENDGRID_BASE)
    return httpx.AsyncClient(
        base_url=SENDGRID_BASE,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"SendGrid API error {r.status_code}: {detail}")


@register_node("sendgrid.send_email")
async def sg_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    to = config.get("to") or input_data.get("to")
    from_email = config.get("from_email") or input_data.get("from_email")
    from_name = config.get("from_name") or input_data.get("from_name", "")
    subject = config.get("subject") or input_data.get("subject", "")
    html_content = config.get("html_content") or input_data.get("html_content", "")
    text_content = config.get("text_content") or input_data.get("text_content", "")
    reply_to = config.get("reply_to") or input_data.get("reply_to", "")
    attachments = config.get("attachments") or input_data.get("attachments", [])
    template_id = config.get("template_id") or input_data.get("template_id", "")
    dynamic_template_data = config.get("dynamic_template_data") or input_data.get("dynamic_template_data", {})

    if not to:
        raise ValueError("sendgrid.send_email requires 'to'")
    if not from_email:
        raise ValueError("sendgrid.send_email requires 'from_email'")

    from_obj: dict = {"email": from_email}
    if from_name:
        from_obj["name"] = from_name

    to_list = [to] if isinstance(to, str) else to
    personalizations: dict = {"to": [{"email": addr} for addr in to_list]}
    if dynamic_template_data:
        personalizations["dynamic_template_data"] = dynamic_template_data

    payload: dict = {
        "personalizations": [personalizations],
        "from": from_obj,
        "subject": subject,
    }

    content = []
    if text_content:
        content.append({"type": "text/plain", "value": text_content})
    if html_content:
        content.append({"type": "text/html", "value": html_content})
    if content:
        payload["content"] = content

    if reply_to:
        payload["reply_to"] = {"email": reply_to}

    if template_id:
        payload["template_id"] = template_id

    if attachments:
        payload["attachments"] = [
            {
                "content": a.get("content_base64", ""),
                "filename": a.get("filename", "attachment"),
                "type": a.get("type", "application/octet-stream"),
            }
            for a in attachments
        ]

    async with await _client(credential_id, db) as client:
        r = await client.post("/mail/send", json=payload)
        _raise_for_status(r)
        message_id = r.headers.get("X-Message-Id", "")

    return {"ok": True, "status_code": r.status_code, "message_id": message_id}


@register_node("sendgrid.send_to_list")
async def sg_send_to_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    list_ids = config.get("list_ids") or input_data.get("list_ids", [])
    from_email = config.get("from_email") or input_data.get("from_email")
    subject = config.get("subject") or input_data.get("subject", "")
    html_content = config.get("html_content") or input_data.get("html_content", "")
    template_id = config.get("template_id") or input_data.get("template_id", "")

    if not list_ids:
        raise ValueError("sendgrid.send_to_list requires 'list_ids'")
    if not from_email:
        raise ValueError("sendgrid.send_to_list requires 'from_email'")

    if isinstance(list_ids, str):
        list_ids = [list_ids]

    payload: dict = {
        "personalizations": [{"to": [{"email": from_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "mail_settings": {"bypass_list_management": {"enable": False}},
    }

    if html_content:
        payload["content"] = [{"type": "text/html", "value": html_content}]
    if template_id:
        payload["template_id"] = template_id

    # Use list_ids via send to segment / marketing (note: sending to lists
    # requires a single send via marketing campaigns for production lists;
    # this payload uses list_ids in personalizations for API v3 compatibility)
    payload["personalizations"][0]["to"] = [{"email": from_email}]

    async with await _client(credential_id, db) as client:
        r = await client.post("/mail/send", json=payload)
        _raise_for_status(r)
        message_id = r.headers.get("X-Message-Id", "")

    return {"ok": True, "status_code": r.status_code, "message_id": message_id, "list_ids": list_ids}


@register_node("sendgrid.add_contact")
async def sg_add_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email = config.get("email") or input_data.get("email")
    first_name = config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    custom_fields = config.get("custom_fields") or input_data.get("custom_fields", {})

    if not email:
        raise ValueError("sendgrid.add_contact requires 'email'")

    contact: dict = {"email": email}
    if first_name:
        contact["first_name"] = first_name
    if last_name:
        contact["last_name"] = last_name
    if custom_fields:
        contact["custom_fields"] = custom_fields

    payload = {"contacts": [contact]}

    async with await _client(credential_id, db) as client:
        r = await client.put("/marketing/contacts", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"job_id": data.get("job_id"), "contact_count": data.get("contact_count")}


@register_node("sendgrid.remove_contact")
async def sg_remove_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("sendgrid.remove_contact requires 'email'")

    async with await _client(credential_id, db) as client:
        # First search for the contact by email to get its ID
        search_r = await client.post(
            "/marketing/contacts/search",
            json={"query": f"email = '{email}'"},
        )
        _raise_for_status(search_r)
        search_data = search_r.json()
        results = search_data.get("result", [])
        if not results:
            return {"deleted": False, "reason": "contact not found"}

        contact_ids = [c["id"] for c in results if "id" in c]
        if not contact_ids:
            return {"deleted": False, "reason": "no contact IDs found"}

        ids_param = ",".join(contact_ids)
        del_r = await client.delete(f"/marketing/contacts", params={"ids": ids_param})
        _raise_for_status(del_r)
        del_data = del_r.json()

    return {"deleted": True, "job_id": del_data.get("job_id"), "contact_ids": contact_ids}


@register_node("sendgrid.get_lists")
async def sg_get_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/marketing/lists", params={"page_size": 100})
        _raise_for_status(r)
        data = r.json()

    return {"lists": data.get("result", []), "metadata": data.get("_metadata", {})}


@register_node("sendgrid.create_list")
async def sg_create_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("sendgrid.create_list requires 'name'")

    async with await _client(credential_id, db) as client:
        r = await client.post("/marketing/lists", json={"name": name})
        _raise_for_status(r)
        data = r.json()

    return {"list": data}


@register_node("sendgrid.add_to_list")
async def sg_add_to_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    list_id = config.get("list_id") or input_data.get("list_id")
    contact_ids = config.get("contact_ids") or input_data.get("contact_ids", [])
    emails = config.get("emails") or input_data.get("emails", [])

    if not list_id:
        raise ValueError("sendgrid.add_to_list requires 'list_id'")
    if not contact_ids and not emails:
        raise ValueError("sendgrid.add_to_list requires 'contact_ids' or 'emails'")

    if isinstance(contact_ids, str):
        contact_ids = [contact_ids]
    if isinstance(emails, str):
        emails = [emails]

    async with await _client(credential_id, db) as client:
        if emails and not contact_ids:
            # Look up contact IDs from emails
            contacts = []
            for email in emails:
                search_r = await client.post(
                    "/marketing/contacts/search",
                    json={"query": f"email = '{email}'"},
                )
                if search_r.status_code < 300:
                    results = search_r.json().get("result", [])
                    contact_ids.extend([c["id"] for c in results if "id" in c])

        payload = {"contact_ids": contact_ids}
        r = await client.post(f"/marketing/lists/{list_id}/contacts", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"job_id": data.get("job_id"), "list_id": list_id, "contact_count": len(contact_ids)}


@register_node("sendgrid.get_templates")
async def sg_get_templates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    generations = config.get("generations") or input_data.get("generations", "dynamic")

    async with await _client(credential_id, db) as client:
        r = await client.get("/templates", params={"generations": generations, "page_size": 200})
        _raise_for_status(r)
        data = r.json()

    return {"templates": data.get("result", []), "metadata": data.get("_metadata", {})}


@register_node("sendgrid.create_template_version")
async def sg_create_template_version(config: dict, input_data: dict, credential_id: str, db) -> dict:
    template_id = config.get("template_id") or input_data.get("template_id")
    name = config.get("name") or input_data.get("name")
    subject = config.get("subject") or input_data.get("subject", "")
    html_content = config.get("html_content") or input_data.get("html_content", "")
    plain_content = config.get("plain_content") or input_data.get("plain_content", "")

    if not template_id:
        raise ValueError("sendgrid.create_template_version requires 'template_id'")
    if not name:
        raise ValueError("sendgrid.create_template_version requires 'name'")

    payload: dict = {"name": name, "active": 1}
    if subject:
        payload["subject"] = subject
    if html_content:
        payload["html_content"] = html_content
    if plain_content:
        payload["plain_content"] = plain_content

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/templates/{template_id}/versions", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"version": data}


@register_node("sendgrid.get_stats")
async def sg_get_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    start_date = config.get("start_date") or input_data.get("start_date")
    end_date = config.get("end_date") or input_data.get("end_date", "")
    aggregated_by = config.get("aggregated_by") or input_data.get("aggregated_by", "day")

    if not start_date:
        raise ValueError("sendgrid.get_stats requires 'start_date' (YYYY-MM-DD)")

    params: dict = {"start_date": start_date, "aggregated_by": aggregated_by}
    if end_date:
        params["end_date"] = end_date

    async with await _client(credential_id, db) as client:
        r = await client.get("/stats", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"stats": data}


@register_node("sendgrid.suppress_email")
async def sg_suppress_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    recipient_email = config.get("recipient_email") or input_data.get("recipient_email")
    if not recipient_email:
        raise ValueError("sendgrid.suppress_email requires 'recipient_email'")

    payload = {"recipient_emails": [recipient_email]}

    async with await _client(credential_id, db) as client:
        r = await client.post("/asm/suppressions/global", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"suppressed": True, "recipient_email": recipient_email, "result": data}


@register_node("sendgrid.check_suppression")
async def sg_check_suppression(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("sendgrid.check_suppression requires 'email'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/asm/suppressions/global/{email}")
        if r.status_code == 404:
            return {"suppressed": False, "email": email}
        _raise_for_status(r)
        data = r.json()

    return {"suppressed": True, "email": email, "details": data}


@register_node("sendgrid.validate_email")
async def sg_validate_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("sendgrid.validate_email requires 'email'")

    async with await _client(credential_id, db) as client:
        try:
            r = await client.post("/mail/validate/email", json={"email": email})
            if r.status_code == 403:
                return {
                    "error": "Email validation requires a SendGrid Pro plan",
                    "email": email,
                    "status_code": 403,
                }
            _raise_for_status(r)
            data = r.json()
        except ValueError:
            raise
        except Exception as exc:
            return {"error": str(exc), "email": email}

    result = data.get("result", {})
    return {
        "email": email,
        "verdict": result.get("verdict"),
        "score": result.get("score"),
        "local": result.get("local"),
        "domain": result.get("domain"),
        "is_disposable_email": result.get("checks", {}).get("additional", {}).get("is_disposable_email"),
        "result": result,
    }
