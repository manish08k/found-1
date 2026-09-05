"""Woodpecker cold email integration — prospects and campaigns."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

WOODPECKER_BASE = "https://api.woodpecker.co/rest/v1"


@register_node("woodpecker.list_prospects")
async def woodpecker_list_prospects(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List active prospects from Woodpecker.

    config/input_data:
      api_key — Woodpecker API key (required, used as HTTP Basic username)
      status  — prospect status filter (default 'ACTIVE')
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    status = merged.get("status", "ACTIVE")

    url = f"{WOODPECKER_BASE}/prospect_list/prospects"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""), params={"status": status})
        r.raise_for_status()
        data = r.json()

    prospects = data if isinstance(data, list) else data.get("prospects", data)
    log.info("woodpecker.list_prospects", status=status, count=len(prospects) if isinstance(prospects, list) else None)
    return {"prospects": prospects}


@register_node("woodpecker.create_prospect")
async def woodpecker_create_prospect(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create one or more prospects in Woodpecker.

    config/input_data:
      api_key    — Woodpecker API key (required)
      email      — prospect email (required, used for single prospect)
      first_name — first name
      last_name  — last name
      company    — company name
      website    — company website
      prospects  — list of prospect dicts (optional, overrides single-prospect fields)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    prospects = merged.get("prospects")

    if not prospects:
        email = merged.get("email") or ""
        if not email:
            raise ValueError("email or prospects list is required for woodpecker.create_prospect")
        prospects = [{
            "email": email,
            "first_name": merged.get("first_name") or "",
            "last_name": merged.get("last_name") or "",
            "company": merged.get("company") or "",
            "website": merged.get("website") or "",
        }]

    url = f"{WOODPECKER_BASE}/prospects"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, auth=(api_key, ""), json=prospects)
        r.raise_for_status()
        data = r.json()

    log.info("woodpecker.create_prospect", count=len(prospects))
    return {"result": data}


@register_node("woodpecker.list_campaigns")
async def woodpecker_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List campaigns from Woodpecker.

    config/input_data:
      api_key — Woodpecker API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    url = f"{WOODPECKER_BASE}/campaigns"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, auth=(api_key, ""))
        r.raise_for_status()
        data = r.json()

    campaigns = data if isinstance(data, list) else data.get("campaigns", data)
    log.info("woodpecker.list_campaigns", count=len(campaigns) if isinstance(campaigns, list) else None)
    return {"campaigns": campaigns}
