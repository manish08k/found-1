"""Parseur document parsing and data extraction integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERVICE_BASE = "https://parseur.com/api/v1"


@register_node("parseur.list_mailboxes")
async def parseur_list_mailboxes(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List mailboxes in Parseur."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for parseur.list_mailboxes")
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get("/mailbox/", headers={"Authorization": f"Token {api_key}"})
        r.raise_for_status()
        data = r.json()
    mailboxes = data if isinstance(data, list) else data.get("results", data.get("mailboxes", []))
    log.info("parseur.list_mailboxes", count=len(mailboxes))
    return {"mailboxes": mailboxes}


@register_node("parseur.list_parsed_data")
async def parseur_list_parsed_data(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List parsed data from a Parseur mailbox."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for parseur.list_parsed_data")
    mailbox_id = merged.get("mailbox_id", "")
    if not mailbox_id:
        raise ValueError("mailbox_id is required for parseur.list_parsed_data")
    params = {}
    if merged.get("limit"):
        params["limit"] = merged["limit"]
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get(
            f"/document/{mailbox_id}/",
            headers={"Authorization": f"Token {api_key}"},
            params=params,
        )
        r.raise_for_status()
        data = r.json()
    items = data if isinstance(data, list) else data.get("results", [])
    log.info("parseur.list_parsed_data", mailbox_id=mailbox_id, count=len(items))
    return {"parsed_data": items, "raw": data}


@register_node("parseur.get_parsed_item")
async def parseur_get_parsed_item(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific parsed item from Parseur."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for parseur.get_parsed_item")
    mailbox_id = merged.get("mailbox_id", "")
    document_id = merged.get("document_id", "")
    if not mailbox_id or not document_id:
        raise ValueError("mailbox_id and document_id are required for parseur.get_parsed_item")
    async with httpx.AsyncClient(base_url=SERVICE_BASE, timeout=30) as client:
        r = await client.get(
            f"/document/{mailbox_id}/{document_id}/",
            headers={"Authorization": f"Token {api_key}"},
        )
        r.raise_for_status()
        data = r.json()
    log.info("parseur.get_parsed_item", document_id=document_id)
    return {"item": data}
