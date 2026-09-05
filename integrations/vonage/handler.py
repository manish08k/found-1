"""Vonage (Nexmo) integration — SMS, voice calls, and number verification."""
import base64
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

NEXMO_REST = "https://rest.nexmo.com"
NEXMO_API = "https://api.nexmo.com"


def _basic_auth_headers(api_key: str, api_secret: str) -> dict:
    credentials = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


@register_node("vonage.send_sms")
async def vonage_send_sms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send an SMS via Vonage.

    config/input_data:
      api_key    — Vonage API key
      api_secret — Vonage API secret
      from       — sender ID or number
      to         — recipient phone number (E.164 format)
      text       — message body
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    from_number = merged.get("from", "")
    to_number = merged.get("to", "")
    text = merged.get("text", "")

    if not to_number:
        raise ValueError("to is required for vonage.send_sms")
    if not text:
        raise ValueError("text is required for vonage.send_sms")

    payload = {
        "api_key": api_key,
        "api_secret": api_secret,
        "from": from_number,
        "to": to_number,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{NEXMO_REST}/sms/json", json=payload)
        r.raise_for_status()
        result = r.json()

    messages = result.get("messages", [])
    log.info("vonage.send_sms", to=to_number, message_count=len(messages))
    return {"messages": messages, "message_count": result.get("message-count", len(messages))}


@register_node("vonage.make_call")
async def vonage_make_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Initiate an outbound voice call via Vonage.

    config/input_data:
      api_key    — Vonage API key
      api_secret — Vonage API secret
      to         — dict with "type" and "number" (e.g. {"type": "phone", "number": "14155550100"})
      from       — dict with "type" and "number"
      ncco       — Nexmo Call Control Object list (optional if answer_url provided)
      answer_url — URL for NCCO (optional if ncco provided)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    to = merged.get("to")
    from_ = merged.get("from")
    if not to:
        raise ValueError("to is required for vonage.make_call")
    if not from_:
        raise ValueError("from is required for vonage.make_call")

    headers = _basic_auth_headers(api_key, api_secret)
    payload: dict = {"to": [to], "from": from_}

    if merged.get("ncco"):
        payload["ncco"] = merged["ncco"]
    elif merged.get("answer_url"):
        payload["answer_url"] = [merged["answer_url"]]
    else:
        raise ValueError("Either ncco or answer_url is required for vonage.make_call")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{NEXMO_API}/v1/calls",
            json=payload,
            headers={**headers, "Content-Type": "application/json"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("vonage.make_call", uuid=result.get("uuid"), status=result.get("status"))
    return {"uuid": result.get("uuid"), "status": result.get("status"), "conversation_uuid": result.get("conversation_uuid")}


@register_node("vonage.get_call")
async def vonage_get_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve details of a voice call.

    config/input_data:
      api_key    — Vonage API key
      api_secret — Vonage API secret
      uuid       — call UUID
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    uuid = merged.get("uuid")
    if not uuid:
        raise ValueError("uuid is required for vonage.get_call")

    headers = _basic_auth_headers(api_key, api_secret)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{NEXMO_API}/v1/calls/{uuid}", headers=headers)
        r.raise_for_status()
        result = r.json()

    log.info("vonage.get_call", uuid=uuid, status=result.get("status"))
    return result


@register_node("vonage.send_verification")
async def vonage_send_verification(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a verification code to a phone number via Vonage Verify.

    config/input_data:
      api_key    — Vonage API key
      api_secret — Vonage API secret
      number     — phone number to verify (E.164 format)
      brand      — name of the brand shown in the verification message
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    number = merged.get("number", "")
    brand = merged.get("brand", "")

    if not number:
        raise ValueError("number is required for vonage.send_verification")
    if not brand:
        raise ValueError("brand is required for vonage.send_verification")

    payload = {
        "api_key": api_key,
        "api_secret": api_secret,
        "number": number,
        "brand": brand,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{NEXMO_API}/verify/json", json=payload)
        r.raise_for_status()
        result = r.json()

    log.info("vonage.send_verification", number=number, request_id=result.get("request_id"), status=result.get("status"))
    return {"request_id": result.get("request_id"), "status": result.get("status")}


@register_node("vonage.check_verification")
async def vonage_check_verification(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Check a verification code submitted by the user.

    config/input_data:
      api_key    — Vonage API key
      api_secret — Vonage API secret
      request_id — request ID from send_verification
      code       — 4-6 digit code entered by the user
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    api_secret = merged.get("api_secret", "")
    request_id = merged.get("request_id", "")
    code = merged.get("code", "")

    if not request_id:
        raise ValueError("request_id is required for vonage.check_verification")
    if not code:
        raise ValueError("code is required for vonage.check_verification")

    payload = {
        "api_key": api_key,
        "api_secret": api_secret,
        "request_id": request_id,
        "code": code,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{NEXMO_API}/verify/check/json", json=payload)
        r.raise_for_status()
        result = r.json()

    log.info("vonage.check_verification", request_id=request_id, status=result.get("status"))
    return {
        "request_id": result.get("request_id"),
        "status": result.get("status"),
        "error_text": result.get("error_text"),
        "price": result.get("price"),
        "currency": result.get("currency"),
    }
