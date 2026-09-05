"""Pendo product analytics integration — guides, pages, accounts, and visitors."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PENDO_BASE = "https://app.pendo.io/api/v1"


def _headers(config: dict, input_data: dict) -> dict:
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required")
    return {"x-pendo-integration-key": api_key}


@register_node("pendo.list_guides")
async def pendo_list_guides(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Pendo guides.

    config:
      api_key — Pendo integration key (required)
      count   — maximum number of guides to return (default 25)
    """
    headers = _headers(config, input_data)
    count = int(config.get("count", 25))

    async with httpx.AsyncClient(base_url=PENDO_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/guide", params={"count": count})
        r.raise_for_status()
        data = r.json()

    guides = data if isinstance(data, list) else data.get("guides", [])
    log.info("pendo.list_guides", count=len(guides))
    return {"guides": guides, "count": len(guides)}


@register_node("pendo.list_pages")
async def pendo_list_pages(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Pendo pages.

    config:
      api_key — Pendo integration key (required)
      count   — maximum number of pages to return (default 25)
    """
    headers = _headers(config, input_data)
    count = int(config.get("count", 25))

    async with httpx.AsyncClient(base_url=PENDO_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/page", params={"count": count})
        r.raise_for_status()
        data = r.json()

    pages = data if isinstance(data, list) else data.get("pages", [])
    log.info("pendo.list_pages", count=len(pages))
    return {"pages": pages, "count": len(pages)}


@register_node("pendo.get_account")
async def pendo_get_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a Pendo account by ID.

    config/input_data:
      api_key    — Pendo integration key (required)
      account_id — account ID (required)
    """
    headers = _headers(config, input_data)
    account_id = config.get("account_id") or input_data.get("account_id")
    if not account_id:
        raise ValueError("account_id is required")

    async with httpx.AsyncClient(base_url=PENDO_BASE, headers=headers, timeout=30) as client:
        r = await client.get(f"/account/{account_id}")
        r.raise_for_status()
        data = r.json()

    log.info("pendo.get_account", account_id=account_id)
    return {"account": data, "account_id": account_id}


@register_node("pendo.list_visitors")
async def pendo_list_visitors(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Pendo visitors.

    config:
      api_key — Pendo integration key (required)
      count   — maximum number of visitors to return (default 25)
    """
    headers = _headers(config, input_data)
    count = int(config.get("count", 25))

    async with httpx.AsyncClient(base_url=PENDO_BASE, headers=headers, timeout=30) as client:
        r = await client.get("/visitor", params={"count": count})
        r.raise_for_status()
        data = r.json()

    visitors = data if isinstance(data, list) else data.get("visitors", [])
    log.info("pendo.list_visitors", count=len(visitors))
    return {"visitors": visitors, "count": len(visitors)}
