"""
WhatsApp — Meta Cloud API integration.
Operator registers their Meta app once in .env.
Supports text, template, media, interactive messages + webhook trigger.
"""
import hashlib
import hmac
import json
import structlog
import httpx
from fastapi import HTTPException, Request

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

WA_API_BASE = "https://graph.facebook.com/v19.0"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


async def _send(phone_number_id: str, access_token: str, payload: dict) -> dict:
    url = f"{WA_API_BASE}/{phone_number_id}/messages"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=payload, headers=_headers(access_token))
        r.raise_for_status()
        return r.json()


@register_node("whatsapp.send_text")
async def wa_send_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    phone_number_id = config.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = config.get("access_token") or settings.WHATSAPP_ACCESS_TOKEN
    to = config.get("to") or input_data.get("to")
    text = config.get("text") or input_data.get("text", "")
    preview_url = config.get("preview_url", False)

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": preview_url, "body": text},
    }
    result = await _send(phone_number_id, access_token, payload)
    return {"message_id": result.get("messages", [{}])[0].get("id")}


@register_node("whatsapp.send_template")
async def wa_send_template(config: dict, input_data: dict, credential_id: str, db) -> dict:
    phone_number_id = config.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = config.get("access_token") or settings.WHATSAPP_ACCESS_TOKEN
    to = config.get("to") or input_data.get("to")
    template_name = config.get("template_name") or input_data.get("template_name")
    language_code = config.get("language_code", "en_US")
    components = config.get("components") or input_data.get("components", [])

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components,
        },
    }
    result = await _send(phone_number_id, access_token, payload)
    return {"message_id": result.get("messages", [{}])[0].get("id")}


@register_node("whatsapp.send_image")
async def wa_send_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    phone_number_id = config.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = config.get("access_token") or settings.WHATSAPP_ACCESS_TOKEN
    to = config.get("to") or input_data.get("to")
    image_url = config.get("image_url") or input_data.get("image_url")
    caption = config.get("caption") or input_data.get("caption", "")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    result = await _send(phone_number_id, access_token, payload)
    return {"message_id": result.get("messages", [{}])[0].get("id")}


@register_node("whatsapp.send_document")
async def wa_send_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    phone_number_id = config.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = config.get("access_token") or settings.WHATSAPP_ACCESS_TOKEN
    to = config.get("to") or input_data.get("to")
    doc_url = config.get("document_url") or input_data.get("document_url")
    filename = config.get("filename", "document.pdf")
    caption = config.get("caption", "")

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "document",
        "document": {"link": doc_url, "filename": filename, "caption": caption},
    }
    result = await _send(phone_number_id, access_token, payload)
    return {"message_id": result.get("messages", [{}])[0].get("id")}


@register_node("whatsapp.send_interactive")
async def wa_send_interactive(config: dict, input_data: dict, credential_id: str, db) -> dict:
    phone_number_id = config.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = config.get("access_token") or settings.WHATSAPP_ACCESS_TOKEN
    to = config.get("to") or input_data.get("to")
    interactive = config.get("interactive") or input_data.get("interactive", {})

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    result = await _send(phone_number_id, access_token, payload)
    return {"message_id": result.get("messages", [{}])[0].get("id")}


@register_node("whatsapp.mark_read")
async def wa_mark_read(config: dict, input_data: dict, credential_id: str, db) -> dict:
    phone_number_id = config.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = config.get("access_token") or settings.WHATSAPP_ACCESS_TOKEN
    message_id = config.get("message_id") or input_data.get("message_id")

    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    await _send(phone_number_id, access_token, payload)
    return {"ok": True}


# ─── Webhook handler for inbound WhatsApp messages ───────────────────────────

def validate_whatsapp_signature(body: bytes, signature: str) -> bool:
    if not settings.WHATSAPP_APP_SECRET:
        return True
    expected = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def parse_whatsapp_webhook(payload: dict) -> list[dict]:
    """Extract individual message events from Meta webhook payload."""
    messages = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                messages.append({
                    "from": msg.get("from"),
                    "message_id": msg.get("id"),
                    "timestamp": msg.get("timestamp"),
                    "type": msg.get("type"),
                    "text": msg.get("text", {}).get("body"),
                    "image": msg.get("image"),
                    "document": msg.get("document"),
                    "audio": msg.get("audio"),
                    "interactive": msg.get("interactive"),
                    "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
                })
    return messages
