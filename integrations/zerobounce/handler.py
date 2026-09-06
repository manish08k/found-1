"""ZeroBounce integration — email validation and deliverability verification."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ZEROBOUNCE_BASE = "https://api.zerobounce.net/v2"


@register_node("zerobounce.validate_email")
async def zerobounce_validate_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Validate a single email address with ZeroBounce.

    config:
      api_key    — ZeroBounce API key (required)
      email      — email address to validate (required)
      ip_address — IP address of the user submitting the email (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    email = merged.get("email")
    if not email:
        raise ValueError("email is required for zerobounce.validate_email")

    params = {"api_key": api_key, "email": email}
    if merged.get("ip_address"):
        params["ip_address"] = merged["ip_address"]

    async with httpx.AsyncClient(base_url=ZEROBOUNCE_BASE, timeout=30) as client:
        r = await client.get("/validate", params=params)
        r.raise_for_status()
        data = r.json()

    status = data.get("status")
    log.info("zerobounce.validate_email", email=email, status=status)
    return {
        "email": email,
        "status": status,
        "sub_status": data.get("sub_status"),
        "is_valid": status == "valid",
        "account": data.get("account"),
        "domain": data.get("domain"),
        "did_you_mean": data.get("did_you_mean"),
        "domain_age_days": data.get("domain_age_days"),
        "free_email": data.get("free_email"),
        "mx_found": data.get("mx_found"),
        "smtp_provider": data.get("smtp_provider"),
        "raw": data,
    }


@register_node("zerobounce.validate_batch")
async def zerobounce_validate_batch(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Validate multiple email addresses in a batch with ZeroBounce.

    config:
      api_key    — ZeroBounce API key (required)
      email_batch — list of email objects with "email_address" and optional "ip_address" keys (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    email_batch = merged.get("email_batch")
    if not email_batch:
        raise ValueError("email_batch is required for zerobounce.validate_batch")

    if isinstance(email_batch, list) and email_batch and isinstance(email_batch[0], str):
        email_batch = [{"email_address": e, "ip_address": ""} for e in email_batch]

    payload = {"api_key": api_key, "email_batch": email_batch}

    async with httpx.AsyncClient(base_url=ZEROBOUNCE_BASE, timeout=60) as client:
        r = await client.post("/validatebatch", json=payload)
        r.raise_for_status()
        data = r.json()

    email_batch_results = data.get("email_batch", [])
    valid_count = sum(1 for item in email_batch_results if item.get("status") == "valid")
    log.info("zerobounce.validate_batch", total=len(email_batch_results), valid=valid_count)
    return {
        "results": email_batch_results,
        "count": len(email_batch_results),
        "valid_count": valid_count,
        "errors": data.get("errors", []),
    }


@register_node("zerobounce.get_credits")
async def zerobounce_get_credits(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get remaining ZeroBounce account credits.

    config:
      api_key — ZeroBounce API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    async with httpx.AsyncClient(base_url=ZEROBOUNCE_BASE, timeout=30) as client:
        r = await client.get("/getcredits", params={"api_key": api_key})
        r.raise_for_status()
        data = r.json()

    credits = data.get("Credits")
    log.info("zerobounce.get_credits", credits=credits)
    return {"credits": credits, "raw": data}
