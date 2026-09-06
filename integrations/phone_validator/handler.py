"""Phone Validator integration — phone number validation and formatting."""
import re
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PHONE_VALIDATOR_BASE = "https://api.phonevalidator.com/v1"


def _normalize_phone(phone: str) -> str:
    """Strip all non-digit characters except leading +."""
    phone = phone.strip()
    if phone.startswith("+"):
        return "+" + re.sub(r"\D", "", phone[1:])
    return re.sub(r"\D", "", phone)


def _local_validate(phone: str) -> dict:
    """Basic local phone validation when no API key is provided."""
    normalized = _normalize_phone(phone)
    digit_count = len(re.sub(r"\D", "", normalized))
    is_valid = 7 <= digit_count <= 15
    is_international = normalized.startswith("+")
    return {
        "phone": phone,
        "normalized": normalized,
        "is_valid": is_valid,
        "digit_count": digit_count,
        "is_international": is_international,
        "validation_source": "local",
    }


@register_node("phone_validator.validate_phone")
async def phone_validator_validate_phone(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Validate a phone number using the PhoneValidator API or local validation.

    config:
      api_key      — PhoneValidator API key (optional; falls back to local validation)
      phone        — phone number to validate (required)
      country_code — ISO 3166-1 alpha-2 country code (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    phone = merged.get("phone")
    if not phone:
        raise ValueError("phone is required for phone_validator.validate_phone")

    if not api_key:
        result = _local_validate(phone)
        log.info("phone_validator.validate_phone", phone=phone, is_valid=result["is_valid"], source="local")
        return result

    params = {"APIKey": api_key, "PhoneNumber": phone}
    if merged.get("country_code"):
        params["CountryCode"] = merged["country_code"]

    async with httpx.AsyncClient(base_url=PHONE_VALIDATOR_BASE, timeout=30) as client:
        r = await client.get("/phonevalidate", params=params)
        r.raise_for_status()
        data = r.json()

    is_valid = data.get("Status") == "Valid"
    log.info("phone_validator.validate_phone", phone=phone, is_valid=is_valid, status=data.get("Status"))
    return {
        "phone": phone,
        "is_valid": is_valid,
        "status": data.get("Status"),
        "line_type": data.get("LineType"),
        "country": data.get("Country"),
        "carrier": data.get("Carrier"),
        "formatted": data.get("PhoneNumber"),
        "validation_source": "api",
        "raw": data,
    }


@register_node("phone_validator.format_phone")
async def phone_validator_format_phone(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Format a phone number into standard representations.

    config:
      phone        — phone number to format (required)
      country_code — default country code for local numbers (optional, e.g. "US")
    """
    merged = {**config, **input_data}
    phone = merged.get("phone")
    if not phone:
        raise ValueError("phone is required for phone_validator.format_phone")

    normalized = _normalize_phone(phone)
    digits_only = re.sub(r"\D", "", normalized)
    digit_count = len(digits_only)

    formatted_e164 = normalized if normalized.startswith("+") else f"+{digits_only}"
    formatted_national = re.sub(r"(\d{3})(\d{3})(\d{4})$", r"(\1) \2-\3", digits_only) if digit_count >= 10 else digits_only

    log.info("phone_validator.format_phone", phone=phone, normalized=normalized)
    return {
        "original": phone,
        "normalized": normalized,
        "e164": formatted_e164,
        "national": formatted_national,
        "digits_only": digits_only,
        "digit_count": digit_count,
        "is_valid_length": 7 <= digit_count <= 15,
    }
