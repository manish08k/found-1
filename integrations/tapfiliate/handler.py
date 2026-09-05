"""Tapfiliate affiliate marketing integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TAPFILIATE_BASE = "https://tapfiliate.com/api/1.6"


def _headers(api_key: str) -> dict:
    return {"Api-Key": api_key, "Content-Type": "application/json"}


@register_node("tapfiliate.list_affiliates")
async def list_affiliates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all affiliates.

    config:
      api_key — Tapfiliate API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    if not api_key:
        raise ValueError("api_key is required for tapfiliate.list_affiliates")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TAPFILIATE_BASE}/affiliates/", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    log.info("tapfiliate.list_affiliates", count=len(data))
    return {"affiliates": data, "count": len(data)}


@register_node("tapfiliate.get_affiliate")
async def get_affiliate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single affiliate by ID.

    config/input_data:
      api_key      — Tapfiliate API key (required)
      affiliate_id — affiliate ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    affiliate_id = merged.get("affiliate_id") or ""

    if not api_key:
        raise ValueError("api_key is required for tapfiliate.get_affiliate")
    if not affiliate_id:
        raise ValueError("affiliate_id is required for tapfiliate.get_affiliate")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TAPFILIATE_BASE}/affiliates/{affiliate_id}/", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    log.info("tapfiliate.get_affiliate", affiliate_id=affiliate_id)
    return {"affiliate": data}


@register_node("tapfiliate.create_affiliate")
async def create_affiliate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new affiliate.

    config/input_data:
      api_key   — Tapfiliate API key (required)
      firstname — affiliate first name (required)
      lastname  — affiliate last name (required)
      email     — affiliate email (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    firstname = merged.get("firstname") or ""
    lastname = merged.get("lastname") or ""
    email = merged.get("email") or ""

    if not api_key:
        raise ValueError("api_key is required for tapfiliate.create_affiliate")
    if not email:
        raise ValueError("email is required for tapfiliate.create_affiliate")

    payload = {
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TAPFILIATE_BASE}/affiliates/", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    log.info("tapfiliate.create_affiliate", email=email)
    return {"affiliate": data, "id": data.get("id")}


@register_node("tapfiliate.list_programs")
async def list_programs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all affiliate programs.

    config:
      api_key — Tapfiliate API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    if not api_key:
        raise ValueError("api_key is required for tapfiliate.list_programs")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TAPFILIATE_BASE}/programs/", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    log.info("tapfiliate.list_programs", count=len(data))
    return {"programs": data, "count": len(data)}


@register_node("tapfiliate.list_commissions")
async def list_commissions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List commissions for a program.

    config/input_data:
      api_key    — Tapfiliate API key (required)
      program_id — program ID to filter by (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    program_id = merged.get("program_id") or ""

    if not api_key:
        raise ValueError("api_key is required for tapfiliate.list_commissions")
    if not program_id:
        raise ValueError("program_id is required for tapfiliate.list_commissions")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{TAPFILIATE_BASE}/commissions/",
            headers=_headers(api_key),
            params={"program-id": program_id},
        )
        r.raise_for_status()
        data = r.json()

    log.info("tapfiliate.list_commissions", program_id=program_id, count=len(data))
    return {"commissions": data, "count": len(data)}


@register_node("tapfiliate.create_conversion")
async def create_conversion(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a conversion for a program.

    config/input_data:
      api_key     — Tapfiliate API key (required)
      program_id  — program ID (required)
      external_id — external reference ID (required)
      amount      — conversion amount (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    program_id = merged.get("program_id") or ""
    external_id = merged.get("external_id") or ""
    amount = merged.get("amount")

    if not api_key:
        raise ValueError("api_key is required for tapfiliate.create_conversion")
    if not program_id:
        raise ValueError("program_id is required for tapfiliate.create_conversion")
    if not external_id:
        raise ValueError("external_id is required for tapfiliate.create_conversion")

    payload: dict = {"program_id": program_id, "external_id": external_id}
    if amount is not None:
        payload["amount"] = amount

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{TAPFILIATE_BASE}/conversions/", json=payload, headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    log.info("tapfiliate.create_conversion", program_id=program_id, external_id=external_id)
    return {"conversion": data, "id": data.get("id")}
