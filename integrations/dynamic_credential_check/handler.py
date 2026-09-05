"""
DynamicCredentialCheck integration.

Validates credentials at runtime by resolving them via the OAuth/credential
store.  No external HTTP calls are made — the check is purely local.

Credential fields resolved at runtime; the node takes a `credential_id`
from its config or input_data and returns whether the credential exists and
which fields it exposes.
"""
import structlog
import httpx  # noqa: F401 – kept for platform consistency

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


@register_node("dynamic_credential_check.validate")
async def validate_credential(
    config: dict, input_data: dict, credential_id: str, db
) -> dict:
    """
    Validate that a credential can be resolved and inspect its fields.

    Config / input keys:
      - credential_id (str): ID of the credential to validate.  Falls back to
        the node-level ``credential_id`` arg if omitted.
      - expected_fields (list[str]): Optional list of field names that must be
        present and non-empty for the credential to be considered valid.

    Returns:
      {
        "valid": bool,
        "credential_id": str,
        "fields": [list of non-empty field names],
        "missing_fields": [fields from expected_fields that are absent/empty],
        "error": str | None
      }
    """
    target_id: str = (
        config.get("credential_id")
        or input_data.get("credential_id")
        or credential_id
    )
    expected_fields: list = (
        config.get("expected_fields")
        or input_data.get("expected_fields")
        or []
    )

    if not target_id:
        return {
            "valid": False,
            "credential_id": None,
            "fields": [],
            "missing_fields": list(expected_fields),
            "error": "No credential_id provided",
        }

    log.info("dynamic_credential_check.validate", credential_id=target_id)

    try:
        creds: dict = await get_credential_data(target_id, db)
    except Exception as exc:  # credential not found or store error
        log.warning(
            "dynamic_credential_check.validate failed",
            credential_id=target_id,
            error=str(exc),
        )
        return {
            "valid": False,
            "credential_id": target_id,
            "fields": [],
            "missing_fields": list(expected_fields),
            "error": str(exc),
        }

    # Collect non-empty field names (exclude internal keys prefixed with "_")
    present_fields = [
        k for k, v in creds.items() if not k.startswith("_") and v not in (None, "", [])
    ]

    missing_fields = [f for f in expected_fields if f not in present_fields]
    valid = bool(present_fields) and len(missing_fields) == 0

    log.info(
        "dynamic_credential_check.validate result",
        credential_id=target_id,
        valid=valid,
        field_count=len(present_fields),
    )

    return {
        "valid": valid,
        "credential_id": target_id,
        "fields": present_fields,
        "missing_fields": missing_fields,
        "error": None,
    }


@register_node("dynamic_credential_check.list_fields")
async def list_credential_fields(
    config: dict, input_data: dict, credential_id: str, db
) -> dict:
    """
    Return all field names (and whether each is populated) for a credential.

    Useful for debugging workflows that need to introspect what a credential
    actually contains without exposing secret values.

    Config / input keys:
      - credential_id (str)

    Returns:
      {
        "credential_id": str,
        "field_summary": [{"name": str, "populated": bool}, ...],
        "total_fields": int
      }
    """
    target_id: str = (
        config.get("credential_id")
        or input_data.get("credential_id")
        or credential_id
    )

    if not target_id:
        raise ValueError("dynamic_credential_check.list_fields requires 'credential_id'")

    log.info("dynamic_credential_check.list_fields", credential_id=target_id)

    creds: dict = await get_credential_data(target_id, db)

    summary = [
        {
            "name": k,
            "populated": v not in (None, "", [], {}),
        }
        for k, v in creds.items()
        if not k.startswith("_")
    ]

    return {
        "credential_id": target_id,
        "field_summary": summary,
        "total_fields": len(summary),
    }


@register_node("dynamic_credential_check.compare")
async def compare_credentials(
    config: dict, input_data: dict, credential_id: str, db
) -> dict:
    """
    Compare two credentials to check they share the same set of field names.

    Config / input keys:
      - credential_id_a (str)
      - credential_id_b (str)

    Returns:
      {
        "match": bool,
        "fields_a": [...],
        "fields_b": [...],
        "only_in_a": [...],
        "only_in_b": [...],
        "common": [...]
      }
    """
    id_a: str = config.get("credential_id_a") or input_data.get("credential_id_a", "")
    id_b: str = config.get("credential_id_b") or input_data.get("credential_id_b", "")

    if not id_a or not id_b:
        raise ValueError(
            "dynamic_credential_check.compare requires 'credential_id_a' and 'credential_id_b'"
        )

    creds_a: dict = await get_credential_data(id_a, db)
    creds_b: dict = await get_credential_data(id_b, db)

    fields_a = {k for k in creds_a if not k.startswith("_")}
    fields_b = {k for k in creds_b if not k.startswith("_")}

    only_in_a = sorted(fields_a - fields_b)
    only_in_b = sorted(fields_b - fields_a)
    common = sorted(fields_a & fields_b)

    return {
        "match": not only_in_a and not only_in_b,
        "fields_a": sorted(fields_a),
        "fields_b": sorted(fields_b),
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
        "common": common,
    }
