"""Venafi Trust Protection Platform integration — certificate lifecycle management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _auth_headers(config: dict) -> dict:
    token = config.get("token", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


@register_node("venafi.list_certificates")
async def venafi_list_certificates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List certificates from Venafi TPP.

    config/input_data:
      base_url — Venafi TPP base URL (e.g. https://tpp.example.com)
      token    — API bearer token
      limit    — max certificates to return (default 100)
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    if not base_url:
        raise ValueError("base_url is required for venafi.list_certificates")

    limit = int(merged.get("limit", 100))
    headers = _auth_headers(merged)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/vedsdk/certificates",
            params={"limit": limit},
            headers=headers,
        )
        r.raise_for_status()
        result = r.json()

    certificates = result.get("Certificates", result) if isinstance(result, dict) else result
    log.info("venafi.list_certificates", count=len(certificates) if isinstance(certificates, list) else "unknown")
    return {"certificates": certificates, "raw": result}


@register_node("venafi.get_certificate")
async def venafi_get_certificate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific certificate by its Distinguished Name.

    config/input_data:
      base_url — Venafi TPP base URL
      token    — API bearer token
      dn       — certificate Distinguished Name
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    dn = merged.get("dn")
    if not base_url:
        raise ValueError("base_url is required for venafi.get_certificate")
    if not dn:
        raise ValueError("dn is required for venafi.get_certificate")

    headers = _auth_headers(merged)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{base_url}/vedsdk/certificates/{dn}",
            headers=headers,
        )
        r.raise_for_status()
        result = r.json()

    log.info("venafi.get_certificate", dn=dn)
    return result


@register_node("venafi.request_certificate")
async def venafi_request_certificate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Request a new certificate from Venafi TPP.

    config/input_data:
      base_url   — Venafi TPP base URL
      token      — API bearer token
      policy_dn  — policy folder DN where certificate will be created
      subject    — certificate subject (CN)
      san_dns    — list of Subject Alternative Name DNS entries
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    if not base_url:
        raise ValueError("base_url is required for venafi.request_certificate")

    policy_dn = merged.get("policy_dn")
    subject = merged.get("subject")
    san_dns = merged.get("san_dns", [])

    if not policy_dn:
        raise ValueError("policy_dn is required for venafi.request_certificate")
    if not subject:
        raise ValueError("subject is required for venafi.request_certificate")

    headers = _auth_headers(merged)
    payload = {
        "PolicyDN": policy_dn,
        "Subject": subject,
        "SubjectAltNames": [{"TypeName": "DNS", "Name": dns} for dns in san_dns],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base_url}/vedsdk/certificates/request",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        result = r.json()

    log.info("venafi.request_certificate", subject=subject, policy_dn=policy_dn)
    return result


@register_node("venafi.revoke_certificate")
async def venafi_revoke_certificate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Revoke a certificate in Venafi TPP.

    config/input_data:
      base_url        — Venafi TPP base URL
      token           — API bearer token
      certificate_dn  — DN of the certificate to revoke
    """
    merged = {**config, **input_data}
    base_url = merged.get("base_url", "").rstrip("/")
    certificate_dn = merged.get("certificate_dn")
    if not base_url:
        raise ValueError("base_url is required for venafi.revoke_certificate")
    if not certificate_dn:
        raise ValueError("certificate_dn is required for venafi.revoke_certificate")

    headers = _auth_headers(merged)
    payload = {"CertificateDN": certificate_dn}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{base_url}/vedsdk/certificates/revoke",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        result = r.json()

    log.info("venafi.revoke_certificate", certificate_dn=certificate_dn)
    return result
