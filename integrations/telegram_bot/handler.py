"""Telegram Bot integration — bot API messaging."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    bot_token = config.get("bot_token", "")
    return f"https://api.telegram.org/bot{bot_token}"


@register_node("telegram_bot.send_message")
async def telegram_bot_send_message(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{_base(merged)}/sendMessage", json={
            "chat_id": merged.get("chat_id", ""),
            "text": merged.get("text", ""),
            "parse_mode": merged.get("parse_mode", "HTML"),
        })
        r.raise_for_status()
    return r.json()


@register_node("telegram_bot.send_photo")
async def telegram_bot_send_photo(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{_base(merged)}/sendPhoto", json={
            "chat_id": merged.get("chat_id", ""),
            "photo": merged.get("photo_url", ""),
            "caption": merged.get("caption", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("telegram_bot.get_updates")
async def telegram_bot_get_updates(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{_base(merged)}/getUpdates", params={"limit": merged.get("limit", 10)})
        r.raise_for_status()
    return {"updates": r.json().get("result", [])}


@register_node("telegram_bot.set_webhook")
async def telegram_bot_set_webhook(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{_base(merged)}/setWebhook", json={"url": merged.get("webhook_url", "")})
        r.raise_for_status()
    return r.json()
