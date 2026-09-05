"""
Mailcheck email validation integration.

Provides single and bulk email validation via the Mailcheck API v1.

Credential fields:
  - api_key : Mailcheck API key (sent as 'apikey' query parameter)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api.mailcheck.ai/v1"


async def _client(credential_id: str, db) -> tuple:
    """Return (httpx.AsyncClient, api_key) for Mailcheck API calls."""
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("Mailcheck credential missing 'api_key'")
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=30.0,
    )
    return client, api_key


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Mailcheck API error {r.status_code}: {detail}")


@register_node("mailcheck.validate_email")
async def mailcheck_validate_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Validate a single email address with Mailcheck."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("mailcheck.validate_email requires 'email'")

    log.info("mailcheck.validate_email", email=email)
    client, api_key = await _client(credential_id, db)
    async with client:
        r = await client.get(f"/email/{email}", params={"apikey": api_key})
        _raise_for_status(r)
        data = r.json()

    return {
        "email": email,
        "valid": data.get("status") == "valid",
        "status": data.get("status"),
        "result": data,
    }


@register_node("mailcheck.bulk_validate")
async def mailcheck_bulk_validate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Validate multiple email addresses in bulk with Mailcheck."""
    emails = config.get("emails") or input_data.get("emails", [])

    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]

    if not emails:
        raise ValueError("mailcheck.bulk_validate requires 'emails' (list or comma-separated string)")

    log.info("mailcheck.bulk_validate", email_count=len(emails))
    client, api_key = await _client(credential_id, db)

    results = []
    async with client:
        for email in emails:
            try:
                r = await client.get(f"/email/{email}", params={"apikey": api_key})
                _raise_for_status(r)
                data = r.json()
                results.append({
                    "email": email,
                    "valid": data.get("status") == "valid",
                    "status": data.get("status"),
                    "result": data,
                })
            except Exception as exc:
                log.warning("mailcheck.bulk_validate email error", email=email, error=str(exc))
                results.append({
                    "email": email,
                    "valid": False,
                    "status": "error",
                    "error": str(exc),
                })

    valid_count = sum(1 for r in results if r.get("valid"))
    return {
        "results": results,
        "total": len(results),
        "valid_count": valid_count,
        "invalid_count": len(results) - valid_count,
    }
