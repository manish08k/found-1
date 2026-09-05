"""
LingvaNex translation API integration.

Provides translation, language detection, and language listing via the LingvaNex B2B API v3.

Credential fields:
  - api_key : LingvaNex API key (Bearer auth)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://api-b2b.backenster.com/b1/api/v3"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("LingvaNex credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"LingvaNex API error {r.status_code}: {detail}")


@register_node("lingvanex.translate")
async def lingvanex_translate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Translate text using the LingvaNex API."""
    text = config.get("text") or input_data.get("text")
    to_language = config.get("to_language") or input_data.get("to_language")
    from_language = config.get("from_language") or input_data.get("from_language", "en_GB")
    platform = config.get("platform") or input_data.get("platform", "api")

    if not text:
        raise ValueError("lingvanex.translate requires 'text'")
    if not to_language:
        raise ValueError("lingvanex.translate requires 'to_language' (e.g. 'de_DE')")

    payload = {
        "platform": platform,
        "from": from_language,
        "to": to_language,
        "data": text,
        "translateMode": "html",
    }

    log.info("lingvanex.translate", from_language=from_language, to_language=to_language)
    async with await _client(credential_id, db) as client:
        r = await client.post("/translate", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "translated_text": data.get("result", ""),
        "from": from_language,
        "to": to_language,
        "response": data,
    }


@register_node("lingvanex.detect_language")
async def lingvanex_detect_language(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Detect the language of the provided text."""
    text = config.get("text") or input_data.get("text")
    platform = config.get("platform") or input_data.get("platform", "api")

    if not text:
        raise ValueError("lingvanex.detect_language requires 'text'")

    payload = {
        "platform": platform,
        "data": text,
    }

    log.info("lingvanex.detect_language")
    async with await _client(credential_id, db) as client:
        r = await client.post("/detect", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "detected_language": data.get("result", ""),
        "response": data,
    }


@register_node("lingvanex.list_languages")
async def lingvanex_list_languages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all supported languages in LingvaNex."""
    platform = config.get("platform") or input_data.get("platform", "api")

    log.info("lingvanex.list_languages")
    async with await _client(credential_id, db) as client:
        r = await client.get("/getLanguages", params={"platform": platform})
        _raise_for_status(r)
        data = r.json()

    languages = data.get("result", data) if isinstance(data, dict) else data
    return {"languages": languages}
