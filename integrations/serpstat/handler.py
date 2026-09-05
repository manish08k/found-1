"""Serpstat SEO integration — domain info and keyword info."""
import json
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SERPSTAT_BASE = "https://api.serpstat.com/v4"


def _token(config: dict, input_data: dict) -> str:
    token = config.get("token") or input_data.get("token")
    if not token:
        raise ValueError("token is required")
    return token


@register_node("serpstat.domain_info")
async def serpstat_domain_info(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch SEO domain information from Serpstat.

    config/input_data:
      token  — Serpstat API token (required)
      domain — domain to analyse (required)
      se     — search engine code (default 'g_us')
    """
    token = _token(config, input_data)
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("domain is required")
    se = config.get("se", "g_us")

    params_obj = json.dumps({"domain": domain, "se": se})
    params = {
        "token": token,
        "method": "SerpstatDomainProcedure.getDomainInfo",
        "params": params_obj,
    }

    async with httpx.AsyncClient(base_url=SERPSTAT_BASE, timeout=30) as client:
        r = await client.get("/", params=params)
        r.raise_for_status()
        data = r.json()

    result = data.get("result", data)
    log.info("serpstat.domain_info", domain=domain, se=se)
    return {"result": result, "domain": domain, "se": se}


@register_node("serpstat.keyword_info")
async def serpstat_keyword_info(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Fetch keyword information from Serpstat.

    config/input_data:
      token   — Serpstat API token (required)
      keyword — keyword to analyse (required)
      se      — search engine code (default 'g_us')
    """
    token = _token(config, input_data)
    keyword = config.get("keyword") or input_data.get("keyword")
    if not keyword:
        raise ValueError("keyword is required")
    se = config.get("se", "g_us")

    params_obj = json.dumps({"keyword": keyword, "se": se})
    params = {
        "token": token,
        "method": "SerpstatKeywordProcedure.getKeywordsInfo",
        "params": params_obj,
    }

    async with httpx.AsyncClient(base_url=SERPSTAT_BASE, timeout=30) as client:
        r = await client.get("/", params=params)
        r.raise_for_status()
        data = r.json()

    result = data.get("result", data)
    log.info("serpstat.keyword_info", keyword=keyword, se=se)
    return {"result": result, "keyword": keyword, "se": se}
