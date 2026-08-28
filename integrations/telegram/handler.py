"""Telegram integration — send messages, files, polls, inline keyboards + webhook."""
import structlog
import httpx

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

TG_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


async def _call(method: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TG_BASE}/{method}", json=payload)
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram error: {data.get('description')}")
        return data.get("result", {})


@register_node("telegram.send_message")
async def tg_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    text = config.get("text") or input_data.get("text", "")
    parse_mode = config.get("parse_mode", "HTML")
    disable_notification = config.get("disable_notification", False)
    reply_markup = config.get("reply_markup") or input_data.get("reply_markup")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_notification": disable_notification,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    result = await _call("sendMessage", payload)
    return {"message_id": result.get("message_id"), "chat_id": chat_id}


@register_node("telegram.send_photo")
async def tg_send_photo(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    photo = config.get("photo") or input_data.get("photo")  # URL or file_id
    caption = config.get("caption") or input_data.get("caption", "")

    result = await _call("sendPhoto", {"chat_id": chat_id, "photo": photo, "caption": caption})
    return {"message_id": result.get("message_id")}


@register_node("telegram.send_document")
async def tg_send_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    document = config.get("document") or input_data.get("document")
    caption = config.get("caption", "")

    result = await _call("sendDocument", {"chat_id": chat_id, "document": document, "caption": caption})
    return {"message_id": result.get("message_id")}


@register_node("telegram.send_poll")
async def tg_send_poll(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    question = config.get("question") or input_data.get("question")
    options = config.get("options") or input_data.get("options", [])
    is_anonymous = config.get("is_anonymous", True)
    poll_type = config.get("type", "regular")

    result = await _call("sendPoll", {
        "chat_id": chat_id,
        "question": question,
        "options": options,
        "is_anonymous": is_anonymous,
        "type": poll_type,
    })
    return {"message_id": result.get("message_id"), "poll_id": result.get("poll", {}).get("id")}


@register_node("telegram.edit_message")
async def tg_edit_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    message_id = config.get("message_id") or input_data.get("message_id")
    text = config.get("text") or input_data.get("text", "")

    result = await _call("editMessageText", {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    })
    return {"ok": True}


@register_node("telegram.delete_message")
async def tg_delete_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    message_id = config.get("message_id") or input_data.get("message_id")

    await _call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    return {"ok": True}


@register_node("telegram.pin_message")
async def tg_pin_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    message_id = config.get("message_id") or input_data.get("message_id")

    await _call("pinChatMessage", {"chat_id": chat_id, "message_id": message_id})
    return {"ok": True}


@register_node("telegram.get_chat_info")
async def tg_get_chat_info(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    result = await _call("getChat", {"chat_id": chat_id})
    return {
        "id": result.get("id"),
        "type": result.get("type"),
        "title": result.get("title"),
        "username": result.get("username"),
        "member_count": result.get("member_count"),
    }


@register_node("telegram.send_inline_keyboard")
async def tg_send_inline_keyboard(config: dict, input_data: dict, credential_id: str, db) -> dict:
    chat_id = config.get("chat_id") or input_data.get("chat_id")
    text = config.get("text") or input_data.get("text", "")
    buttons = config.get("buttons") or input_data.get("buttons", [])
    # buttons: [[{"text": "Click", "callback_data": "action"}]]

    reply_markup = {"inline_keyboard": buttons}
    result = await _call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": reply_markup,
    })
    return {"message_id": result.get("message_id")}


# ─── Webhook setup ────────────────────────────────────────────────────────────

async def set_telegram_webhook(webhook_url: str) -> dict:
    result = await _call("setWebhook", {
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query", "inline_query"],
    })
    return result


def parse_telegram_update(update: dict) -> dict:
    """Normalize a Telegram update into a standard event dict."""
    if "message" in update:
        msg = update["message"]
        return {
            "type": "message",
            "chat_id": msg["chat"]["id"],
            "message_id": msg["message_id"],
            "from_id": msg.get("from", {}).get("id"),
            "from_username": msg.get("from", {}).get("username"),
            "text": msg.get("text", ""),
            "date": msg.get("date"),
        }
    if "callback_query" in update:
        cb = update["callback_query"]
        return {
            "type": "callback_query",
            "callback_id": cb["id"],
            "chat_id": cb["message"]["chat"]["id"],
            "message_id": cb["message"]["message_id"],
            "from_id": cb.get("from", {}).get("id"),
            "data": cb.get("data"),
        }
    return {"type": "unknown", "raw": update}
