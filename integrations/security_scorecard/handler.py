"""SecurityScorecard integration — company risk ratings and portfolio management.

Credential fields:
  - api_key : SecurityScorecard API key

Auth: Bearer token
Base URL: https://api.securityscorecard.io/

Nodes:
  - security_scorecard.get_company_score : get scorecard for a domain
  - security_scorecard.get_portfolio     : list all portfolios
  - security_scorecard.list_factors      : list score factors for a domain
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.securityscorecard.io"


# ---------------------------------------------------------------------------
# Client helper
# ---------------------------------------------------------------------------

async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("SecurityScorecard credential is missing 'api_key'")

    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Token {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("security_scorecard.get_company_score")
async def get_company_score(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get the SecurityScorecard score for a given domain."""
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("'domain' is required (e.g. 'example.com')")

    log.info("security_scorecard.get_company_score", domain=domain)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/companies/{domain}")
        r.raise_for_status()
        data = r.json()

    log.info(
        "security_scorecard.get_company_score.done",
        domain=domain,
        score=data.get("score"),
        grade=data.get("grade"),
    )
    return {
        "domain": domain,
        "score": data.get("score"),
        "grade": data.get("grade"),
        "grade_url": data.get("grade_url"),
        "industry": data.get("industry"),
        "size": data.get("size"),
        "name": data.get("name"),
        "raw": data,
    }


@register_node("security_scorecard.get_portfolio")
async def get_portfolio(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all SecurityScorecard portfolios for the authenticated user."""
    log.info("security_scorecard.get_portfolio")
    async with await _client(credential_id, db) as client:
        r = await client.get("/portfolios")
        r.raise_for_status()
        data = r.json()

    portfolios = data.get("entries", data.get("portfolios", []))
    log.info("security_scorecard.get_portfolio.done", count=len(portfolios))
    return {
        "portfolios": portfolios,
        "count": len(portfolios),
        "total": data.get("total", len(portfolios)),
    }


@register_node("security_scorecard.list_factors")
async def list_factors(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all score factors and their details for a given domain."""
    domain = config.get("domain") or input_data.get("domain")
    if not domain:
        raise ValueError("'domain' is required")

    log.info("security_scorecard.list_factors", domain=domain)
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/companies/{domain}/factors")
        r.raise_for_status()
        data = r.json()

    factors = data.get("entries", data.get("factors", []))
    log.info("security_scorecard.list_factors.done", domain=domain, count=len(factors))
    return {
        "domain": domain,
        "factors": factors,
        "count": len(factors),
        "raw": data,
    }
