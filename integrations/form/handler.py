"""Form integration — HTML form data processing."""
import json
import structlog
import httpx
from urllib.parse import parse_qs, urlencode

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _parse_urlencoded(raw: str) -> dict:
    """Parse a URL-encoded form string into a flat dict."""
    parsed = parse_qs(raw, keep_blank_values=True)
    # Flatten single-value lists to scalars
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}


@register_node("form.parse_form_data")
async def form_parse_form_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse URL-encoded or JSON form data into a structured dict."""
    raw = config.get("data") or input_data.get("data") or input_data.get("body", "")
    content_type = (
        config.get("content_type")
        or input_data.get("content_type")
        or input_data.get("headers", {}).get("content-type", "")
        or ""
    ).lower()

    log.info("form.parse_form_data", content_type=content_type)

    if "application/json" in content_type:
        if isinstance(raw, dict):
            fields = raw
        else:
            try:
                fields = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"form.parse_form_data: invalid JSON body — {exc}") from exc
    else:
        # Default: treat as URL-encoded
        if isinstance(raw, dict):
            fields = raw
        elif isinstance(raw, str):
            fields = _parse_urlencoded(raw)
        else:
            fields = {}

    return {"fields": fields, "field_count": len(fields)}


@register_node("form.validate_fields")
async def form_validate_fields(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Validate that all required fields are present and non-empty."""
    required = config.get("required_fields") or input_data.get("required_fields") or []
    fields = config.get("fields") or input_data.get("fields") or input_data

    if isinstance(required, str):
        required = [f.strip() for f in required.split(",") if f.strip()]

    log.info("form.validate_fields", required=required)

    missing = [f for f in required if not fields.get(f)]
    if missing:
        raise ValueError(f"form.validate_fields: missing required fields: {missing}")

    return {"valid": True, "fields": fields, "validated_fields": required}


@register_node("form.build_response")
async def form_build_response(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Build an HTTP-style form response payload."""
    status_code = int(config.get("status_code") or input_data.get("status_code", 200))
    body = config.get("body") or input_data.get("body") or input_data.get("fields") or {}
    content_type = config.get("content_type") or input_data.get("content_type", "application/json")
    redirect_url = config.get("redirect_url") or input_data.get("redirect_url")

    log.info("form.build_response", status_code=status_code, content_type=content_type)

    response: dict = {
        "status_code": status_code,
        "content_type": content_type,
        "body": body,
    }
    if redirect_url:
        response["redirect_url"] = redirect_url

    if "application/json" in content_type:
        response["body_serialized"] = json.dumps(body)
    elif "application/x-www-form-urlencoded" in content_type:
        if isinstance(body, dict):
            response["body_serialized"] = urlencode(body)

    return response
