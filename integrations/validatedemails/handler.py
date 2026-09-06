"""ValidatedEmails integration — email validation and batch verification."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

VALIDATEDEMAILS_BASE = "https://api.validatedemails.com/v1"


def _validatedemails_headers(access_token: str) -> dict:
    return {"x-access-token": access_token, "Content-Type": "application/json"}


@register_node("validatedemails.validate_email")
async def validatedemails_validate_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Validate a single email address with ValidatedEmails.

    config:
      access_token — ValidatedEmails API access token (required)
      email        — email address to validate (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    email = merged.get("email")
    if not email:
        raise ValueError("email is required for validatedemails.validate_email")

    params = {"email": email}

    async with httpx.AsyncClient(base_url=VALIDATEDEMAILS_BASE, timeout=30) as client:
        r = await client.get(
            "/validate",
            headers=_validatedemails_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    is_valid = data.get("valid", data.get("is_valid", False))
    status = data.get("status", data.get("result"))
    log.info("validatedemails.validate_email", email=email, is_valid=is_valid, status=status)
    return {
        "email": email,
        "is_valid": is_valid,
        "status": status,
        "disposable": data.get("disposable"),
        "role_account": data.get("role_account"),
        "free_provider": data.get("free_provider"),
        "mx_found": data.get("mx_found"),
        "raw": data,
    }


@register_node("validatedemails.validate_batch")
async def validatedemails_validate_batch(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Validate multiple email addresses in batch with ValidatedEmails.

    config:
      access_token — ValidatedEmails API access token (required)
      emails       — list of email addresses to validate (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    emails = merged.get("emails")
    if not emails:
        raise ValueError("emails is required for validatedemails.validate_batch")
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]

    results = []
    async with httpx.AsyncClient(base_url=VALIDATEDEMAILS_BASE, timeout=60) as client:
        for email in emails:
            r = await client.get(
                "/validate",
                headers=_validatedemails_headers(access_token),
                params={"email": email},
            )
            r.raise_for_status()
            item = r.json()
            item["queried_email"] = email
            results.append(item)

    valid_count = sum(1 for item in results if item.get("valid", item.get("is_valid", False)))
    log.info("validatedemails.validate_batch", total=len(emails), valid=valid_count)
    return {"results": results, "count": len(results), "valid_count": valid_count}
