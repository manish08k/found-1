"""DocuSign integration — envelopes, documents, and recipients."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DEFAULT_BASE_URL = "demo.docusign.net"


def _docusign_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def _envelopes_url(base_url: str, account_id: str) -> str:
    host = base_url.rstrip("/")
    if not host.startswith("http"):
        host = f"https://{host}"
    return f"{host}/restapi/v2.1/accounts/{account_id}/envelopes"


@register_node("docusign.send_envelope")
async def docusign_send_envelope(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Create and send a DocuSign envelope for signing.

    config:
      access_token — OAuth bearer token (required)
      account_id   — DocuSign account ID (required)
      base_url     — API base URL, default demo.docusign.net (optional)
      email_subject — subject line of the signing request email (required)
      documents    — list of document dicts with documentId, name, fileExtension, documentBase64 (required)
      recipients   — dict with signers list, each having email, name, recipientId, tabs (required)
      status       — "sent" to send immediately, "created" for draft (optional, default "sent")
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    account_id = merged.get("account_id")
    base_url = merged.get("base_url", DEFAULT_BASE_URL)
    email_subject = merged.get("email_subject")
    documents = merged.get("documents")
    recipients = merged.get("recipients")

    if not account_id or not email_subject or not documents or not recipients:
        raise ValueError(
            "account_id, email_subject, documents, and recipients are required for docusign.send_envelope"
        )

    payload = {
        "emailSubject": email_subject,
        "documents": documents,
        "recipients": recipients,
        "status": merged.get("status", "sent"),
    }

    url = _envelopes_url(base_url, account_id)

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=_docusign_headers(access_token), json=payload)
        r.raise_for_status()
        envelope = r.json()

    log.info(
        "docusign.send_envelope",
        envelope_id=envelope.get("envelopeId"),
        status=envelope.get("status"),
    )
    return {"envelope": envelope, "envelope_id": envelope.get("envelopeId")}


@register_node("docusign.get_envelope")
async def docusign_get_envelope(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Get details and status of a DocuSign envelope.

    config:
      access_token — OAuth bearer token (required)
      account_id   — DocuSign account ID (required)
      base_url     — API base URL (optional, default demo.docusign.net)
      envelope_id  — envelope ID to retrieve (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    account_id = merged.get("account_id")
    base_url = merged.get("base_url", DEFAULT_BASE_URL)
    envelope_id = merged.get("envelope_id")

    if not account_id or not envelope_id:
        raise ValueError("account_id and envelope_id are required for docusign.get_envelope")

    url = f"{_envelopes_url(base_url, account_id)}/{envelope_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_docusign_headers(access_token))
        r.raise_for_status()
        envelope = r.json()

    log.info(
        "docusign.get_envelope",
        envelope_id=envelope_id,
        status=envelope.get("status"),
    )
    return {"envelope": envelope, "envelope_id": envelope_id, "status": envelope.get("status")}


@register_node("docusign.list_envelopes")
async def docusign_list_envelopes(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List envelopes in a DocuSign account.

    config:
      access_token     — OAuth bearer token (required)
      account_id       — DocuSign account ID (required)
      base_url         — API base URL (optional, default demo.docusign.net)
      from_date        — start date in ISO 8601 (required by DocuSign)
      status           — filter by status: "sent", "delivered", "completed", "declined" (optional)
      count            — max envelopes to return (optional, default 100)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    account_id = merged.get("account_id")
    base_url = merged.get("base_url", DEFAULT_BASE_URL)
    from_date = merged.get("from_date")

    if not account_id or not from_date:
        raise ValueError("account_id and from_date are required for docusign.list_envelopes")

    params: dict = {"from_date": from_date, "count": merged.get("count", 100)}
    if merged.get("status"):
        params["status"] = merged["status"]

    url = _envelopes_url(base_url, account_id)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_docusign_headers(access_token), params=params)
        r.raise_for_status()
        data = r.json()

    envelopes = data.get("envelopes", [])
    log.info("docusign.list_envelopes", account_id=account_id, count=len(envelopes))
    return {
        "envelopes": envelopes,
        "count": len(envelopes),
        "total_set_size": data.get("totalSetSize"),
    }


@register_node("docusign.get_document")
async def docusign_get_document(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Download a document from a DocuSign envelope.

    config:
      access_token — OAuth bearer token (required)
      account_id   — DocuSign account ID (required)
      base_url     — API base URL (optional, default demo.docusign.net)
      envelope_id  — envelope ID (required)
      document_id  — document ID within the envelope, or "combined" for all (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    account_id = merged.get("account_id")
    base_url = merged.get("base_url", DEFAULT_BASE_URL)
    envelope_id = merged.get("envelope_id")
    document_id = merged.get("document_id")

    if not account_id or not envelope_id or not document_id:
        raise ValueError(
            "account_id, envelope_id, and document_id are required for docusign.get_document"
        )

    url = f"{_envelopes_url(base_url, account_id)}/{envelope_id}/documents/{document_id}"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url, headers=_docusign_headers(access_token))
        r.raise_for_status()
        content = r.content

    content_type = r.headers.get("content-type", "application/pdf")
    log.info(
        "docusign.get_document",
        envelope_id=envelope_id,
        document_id=document_id,
        size=len(content),
    )
    return {
        "envelope_id": envelope_id,
        "document_id": document_id,
        "content_type": content_type,
        "size": len(content),
        "content_hex": content.hex(),
    }


@register_node("docusign.list_recipients")
async def docusign_list_recipients(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List recipients of a DocuSign envelope.

    config:
      access_token — OAuth bearer token (required)
      account_id   — DocuSign account ID (required)
      base_url     — API base URL (optional, default demo.docusign.net)
      envelope_id  — envelope ID (required)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    account_id = merged.get("account_id")
    base_url = merged.get("base_url", DEFAULT_BASE_URL)
    envelope_id = merged.get("envelope_id")

    if not account_id or not envelope_id:
        raise ValueError("account_id and envelope_id are required for docusign.list_recipients")

    url = f"{_envelopes_url(base_url, account_id)}/{envelope_id}/recipients"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=_docusign_headers(access_token))
        r.raise_for_status()
        data = r.json()

    signers = data.get("signers", [])
    log.info("docusign.list_recipients", envelope_id=envelope_id, signer_count=len(signers))
    return {"recipients": data, "signers": signers, "envelope_id": envelope_id}
