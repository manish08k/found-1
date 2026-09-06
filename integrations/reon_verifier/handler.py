"""Reoon Email Verifier integration — email verification with power mode."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

REOON_BASE = "https://api.reoon.com/email-verifier/v1"


@register_node("reon_verifier.verify_email")
async def reon_verify_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify a single email address using Reoon Email Verifier in power mode.

    config:
      api_key — Reoon API key (required)
      email   — email address to verify (required)
      mode    — verification mode (optional, default "power")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    email = merged.get("email")
    if not email:
        raise ValueError("email is required for reon_verifier.verify_email")

    params = {
        "email": email,
        "key": api_key,
        "mode": merged.get("mode", "power"),
    }

    async with httpx.AsyncClient(base_url=REOON_BASE, timeout=30) as client:
        r = await client.get("/", params=params)
        r.raise_for_status()
        data = r.json()

    status = data.get("status")
    log.info("reon_verifier.verify_email", email=email, status=status)
    return {
        "email": email,
        "status": status,
        "is_valid": status == "valid",
        "is_disposable": data.get("is_disposable"),
        "is_role_account": data.get("is_role_account"),
        "mx_records_found": data.get("mx_records_found"),
        "smtp_check": data.get("smtp_check"),
        "raw": data,
    }


@register_node("reon_verifier.bulk_verify")
async def reon_bulk_verify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify multiple email addresses using Reoon Email Verifier.

    config:
      api_key — Reoon API key (required)
      emails  — list of email addresses to verify (required)
      mode    — verification mode (optional, default "power")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    emails = merged.get("emails")
    mode = merged.get("mode", "power")
    if not emails:
        raise ValueError("emails is required for reon_verifier.bulk_verify")
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]

    results = []
    async with httpx.AsyncClient(base_url=REOON_BASE, timeout=60) as client:
        for email in emails:
            r = await client.get("/", params={"email": email, "key": api_key, "mode": mode})
            r.raise_for_status()
            item = r.json()
            item["queried_email"] = email
            results.append(item)

    valid_count = sum(1 for item in results if item.get("status") == "valid")
    log.info("reon_verifier.bulk_verify", total=len(emails), valid=valid_count)
    return {"results": results, "count": len(results), "valid_count": valid_count}
