"""NeverBounce integration — email verification and list cleaning."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

NEVERBOUNCE_BASE = "https://api.neverbounce.com/v4"


@register_node("neverbounce.verify_email")
async def neverbounce_verify_email(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify a single email address with NeverBounce.

    config:
      api_key         — NeverBounce API key (required)
      email           — email address to verify (required)
      address_info    — include address info in response (optional, default 1)
      credits_info    — include credits info in response (optional, default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    email = merged.get("email")
    if not email:
        raise ValueError("email is required for neverbounce.verify_email")

    params = {
        "api_key": api_key,
        "email": email,
        "address_info": merged.get("address_info", 1),
        "credits_info": merged.get("credits_info", 1),
    }

    async with httpx.AsyncClient(base_url=NEVERBOUNCE_BASE, timeout=30) as client:
        r = await client.get("/single/check", params=params)
        r.raise_for_status()
        data = r.json()

    result = data.get("result")
    log.info("neverbounce.verify_email", email=email, result=result)
    return {
        "email": email,
        "result": result,
        "flags": data.get("flags", []),
        "suggested_correction": data.get("suggested_correction"),
        "address_info": data.get("address_info"),
        "credits_info": data.get("credits_info"),
        "raw": data,
    }


@register_node("neverbounce.bulk_verify")
async def neverbounce_bulk_verify(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Submit a list of emails for bulk verification with NeverBounce.

    config:
      api_key    — NeverBounce API key (required)
      emails     — list of email addresses to verify (required)
      list_name  — name for the bulk verification job (optional)
      auto_parse — auto parse the list (optional, default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    emails = merged.get("emails")
    if not emails:
        raise ValueError("emails is required for neverbounce.bulk_verify")
    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]

    input_list = [{"id": idx, "email": email} for idx, email in enumerate(emails)]

    payload = {
        "api_key": api_key,
        "input_location": 0,
        "input": input_list,
        "auto_parse": merged.get("auto_parse", 1),
    }
    if merged.get("list_name"):
        payload["list_name"] = merged["list_name"]

    async with httpx.AsyncClient(base_url=NEVERBOUNCE_BASE, timeout=60) as client:
        r = await client.post("/list/create", json=payload)
        r.raise_for_status()
        data = r.json()

    job_id = data.get("id")
    log.info("neverbounce.bulk_verify", job_id=job_id, total=len(emails))
    return {"job_id": job_id, "total": len(emails), "status": data.get("status"), "raw": data}


@register_node("neverbounce.get_account_info")
async def neverbounce_get_account_info(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get NeverBounce account information including credits balance.

    config:
      api_key — NeverBounce API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")

    async with httpx.AsyncClient(base_url=NEVERBOUNCE_BASE, timeout=30) as client:
        r = await client.get("/account/info", params={"api_key": api_key})
        r.raise_for_status()
        data = r.json()

    log.info(
        "neverbounce.get_account_info",
        credits_remaining=data.get("credits_info", {}).get("paid_credits_remaining"),
    )
    return {
        "account_info": data,
        "credits_info": data.get("credits_info"),
        "billing_type": data.get("billing_type"),
    }
