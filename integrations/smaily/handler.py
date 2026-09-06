"""Smaily integration — email marketing platform."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return f"https://{config.get('subdomain', '')}.sendsmaily.net/api"


def _auth(config: dict):
    return (config.get("username", ""), config.get("password", ""))


@register_node("smaily.send_email")
async def smaily_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{_base(merged)}/message/send.php", auth=_auth(merged), json={
            "to": [merged.get("to", "")],
            "subject": merged.get("subject", ""),
            "html": merged.get("html_content", ""),
        })
        r.raise_for_status()
    return r.json()


@register_node("smaily.add_subscriber")
async def smaily_add_subscriber(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{_base(merged)}/contact.php", auth=_auth(merged), json={
            "email": merged.get("email", ""),
            "first_name": merged.get("first_name", ""),
        })
        r.raise_for_status()
    return r.json()
