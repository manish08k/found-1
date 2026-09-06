"""Certopus integration — certificate generation and management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.certopus.com/v1"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("certopus.issue_certificate")
async def certopus_issue_certificate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{BASE}/certificates/issue", json={
            "template_id": merged.get("template_id", ""),
            "recipient_name": merged.get("recipient_name", ""),
            "recipient_email": merged.get("recipient_email", ""),
            "custom_fields": merged.get("custom_fields", {}),
        })
        r.raise_for_status()
    return r.json()


@register_node("certopus.get_certificate")
async def certopus_get_certificate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    cert_id = merged.get("certificate_id", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.get(f"{BASE}/certificates/{cert_id}")
        r.raise_for_status()
    return r.json()
