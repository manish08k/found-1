"""SOAP integration — SOAP/XML web services."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("soap.call")
async def soap_call(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    endpoint = merged.get("endpoint", "")
    action = merged.get("soap_action", "")
    body = merged.get("body", "")
    if not body:
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>{merged.get("xml_body", "")}</soap:Body>
</soap:Envelope>"""
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": action,
        **(merged.get("headers", {})),
    }
    async with httpx.AsyncClient(headers=headers, timeout=merged.get("timeout", 30)) as client:
        r = await client.post(endpoint, content=body)
        r.raise_for_status()
    return {"response": r.text, "status_code": r.status_code}
