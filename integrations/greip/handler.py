"""Greip integration — IP lookup, ASN, country, email/phone validation."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GREIP_BASE = "https://gregeoip.com"


def _greip_params(api_key: str, **kwargs) -> dict:
    params = {"key": api_key, "format": "JSON"}
    params.update({k: v for k, v in kwargs.items() if v is not None})
    return params


@register_node("greip.ip_lookup")
async def greip_ip_lookup(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Look up geolocation and metadata for an IP address.

    config:
      api_key  — Greip API key (required)
      ip       — IP address to look up (required)
      lang     — response language (optional, default "EN")
      params   — list of extra data modules e.g. ["security", "currency"] (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    ip = merged.get("ip")
    if not ip:
        raise ValueError("ip is required for greip.ip_lookup")

    params = _greip_params(api_key, ip=ip, lang=merged.get("lang", "EN"))
    if merged.get("params"):
        params["params"] = ",".join(merged["params"])

    async with httpx.AsyncClient(base_url=GREIP_BASE, timeout=30) as client:
        r = await client.get("/IPLookup", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("greip.ip_lookup", ip=ip, country=data.get("data", {}).get("countryCode"))
    return {"data": data, "ip": ip}


@register_node("greip.asn_lookup")
async def greip_asn_lookup(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Look up information about an Autonomous System Number.

    config:
      api_key — Greip API key (required)
      asn     — ASN to look up e.g. "AS1234" (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    asn = merged.get("asn")
    if not asn:
        raise ValueError("asn is required for greip.asn_lookup")

    params = _greip_params(api_key, asn=asn)

    async with httpx.AsyncClient(base_url=GREIP_BASE, timeout=30) as client:
        r = await client.get("/ASNLookup", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("greip.asn_lookup", asn=asn)
    return {"data": data, "asn": asn}


@register_node("greip.country_lookup")
async def greip_country_lookup(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Look up information about a country by country code.

    config:
      api_key       — Greip API key (required)
      country_code  — ISO 3166-1 alpha-2 country code e.g. "US" (required)
      lang          — response language (optional, default "EN")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    country_code = merged.get("country_code")
    if not country_code:
        raise ValueError("country_code is required for greip.country_lookup")

    params = _greip_params(
        api_key, CountryCode=country_code, lang=merged.get("lang", "EN")
    )

    async with httpx.AsyncClient(base_url=GREIP_BASE, timeout=30) as client:
        r = await client.get("/Country", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("greip.country_lookup", country_code=country_code)
    return {"data": data, "country_code": country_code}


@register_node("greip.bulk_ip_lookup")
async def greip_bulk_ip_lookup(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Perform a bulk lookup of multiple IP addresses.

    config:
      api_key — Greip API key (required)
      ips     — list of IP addresses to look up (required)
      lang    — response language (optional, default "EN")
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    ips = merged.get("ips", [])
    if not ips:
        raise ValueError("ips list is required for greip.bulk_ip_lookup")

    payload = {
        "key": api_key,
        "ips": ips,
        "format": "JSON",
        "lang": merged.get("lang", "EN"),
    }

    async with httpx.AsyncClient(base_url=GREIP_BASE, timeout=60) as client:
        r = await client.post("/BulkLookup", json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("greip.bulk_ip_lookup", count=len(ips))
    return {"data": data, "count": len(ips)}


@register_node("greip.validate_email")
async def greip_validate_email(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Validate an email address for format, domain, and spam risks.

    config:
      api_key — Greip API key (required)
      email   — email address to validate (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    email = merged.get("email")
    if not email:
        raise ValueError("email is required for greip.validate_email")

    params = _greip_params(api_key, email=email)

    async with httpx.AsyncClient(base_url=GREIP_BASE, timeout=30) as client:
        r = await client.get("/validateEmail", params=params)
        r.raise_for_status()
        data = r.json()

    is_valid = data.get("data", {}).get("isValid", False)
    log.info("greip.validate_email", email=email, is_valid=is_valid)
    return {"data": data, "email": email, "is_valid": is_valid}


@register_node("greip.validate_phone")
async def greip_validate_phone(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Validate a phone number and retrieve carrier/type information.

    config:
      api_key      — Greip API key (required)
      phone        — phone number to validate (required)
      country_code — ISO country code to help parse the number e.g. "US" (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    phone = merged.get("phone")
    if not phone:
        raise ValueError("phone is required for greip.validate_phone")

    params = _greip_params(
        api_key, phone=phone, countryCode=merged.get("country_code")
    )

    async with httpx.AsyncClient(base_url=GREIP_BASE, timeout=30) as client:
        r = await client.get("/validatePhone", params=params)
        r.raise_for_status()
        data = r.json()

    is_valid = data.get("data", {}).get("isValid", False)
    log.info("greip.validate_phone", phone=phone, is_valid=is_valid)
    return {"data": data, "phone": phone, "is_valid": is_valid}
