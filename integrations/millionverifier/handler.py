"""MillionVerifier integration — email address verification."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MILLIONVERIFIER_BASE = "https://bulkapi.millionverifier.com"


@register_node("millionverifier.verify_email")
async def millionverifier_verify_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify a single email address with MillionVerifier.

    config:
      api_key — MillionVerifier API key (required)
      email   — email address to verify (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    email = merged.get("email")
    if not email:
        raise ValueError("email is required for millionverifier.verify_email")

    params = {"email": email, "key": api_key}

    async with httpx.AsyncClient(base_url=MILLIONVERIFIER_BASE, timeout=30) as client:
        r = await client.get("/verify/v3/", params=params)
        r.raise_for_status()
        data = r.json()

    result_code = data.get("resultcode")
    result = data.get("result")
    log.info("millionverifier.verify_email", email=email, result=result, resultcode=result_code)
    return {
        "email": email,
        "result": result,
        "resultcode": result_code,
        "subresult": data.get("subresult"),
        "free": data.get("free"),
        "role": data.get("role"),
        "disposable": data.get("disposable"),
        "raw": data,
    }


@register_node("millionverifier.bulk_verify")
async def millionverifier_bulk_verify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify multiple email addresses with MillionVerifier.

    config:
      api_key — MillionVerifier API key (required)
      emails  — list of email addresses to verify (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    emails = merged.get("emails")
    if not emails:
        raise ValueError("emails is required for millionverifier.bulk_verify")
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]

    results = []
    async with httpx.AsyncClient(base_url=MILLIONVERIFIER_BASE, timeout=60) as client:
        for email in emails:
            r = await client.get("/verify/v3/", params={"email": email, "key": api_key})
            r.raise_for_status()
            item = r.json()
            item["queried_email"] = email
            results.append(item)

    log.info("millionverifier.bulk_verify", total=len(emails), processed=len(results))
    return {"results": results, "count": len(results)}
