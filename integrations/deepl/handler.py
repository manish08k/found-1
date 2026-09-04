"""
DeepL Translation API integration.

Credential fields:
  - api_key: DeepL authentication key (DeepL-Auth-Key header)
  - pro: boolean — use api.deepl.com (True) or api-free.deepl.com (False)

Auth: DeepL-Auth-Key header
Base URL: https://api.deepl.com/v2 (pro) or https://api-free.deepl.com/v2 (free)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    is_pro = creds.get("pro", False)
    if isinstance(is_pro, str):
        is_pro = is_pro.lower() in ("true", "1", "yes")
    if not api_key:
        raise ValueError("DeepL credential is missing 'api_key'")
    if is_pro:
        base_url = "https://api.deepl.com/v2"
    else:
        base_url = "https://api-free.deepl.com/v2"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={
            "Authorization": f"DeepL-Auth-Key {api_key}",
            "Content-Type": "application/json",
        },
        timeout=60.0,
    )


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"DeepL API error {r.status_code}: {detail}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("deepl.translate_text")
async def deepl_translate_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /translate — translate one or more text strings."""
    text = config.get("text") or input_data.get("text")
    target_lang = config.get("target_lang") or input_data.get("target_lang")
    if not text:
        raise ValueError("deepl.translate_text requires 'text'")
    if not target_lang:
        raise ValueError("deepl.translate_text requires 'target_lang'")
    if isinstance(text, str):
        text = [text]
    body: dict = {"text": text, "target_lang": target_lang.upper()}
    source_lang = config.get("source_lang") or input_data.get("source_lang")
    if source_lang:
        body["source_lang"] = source_lang.upper()
    formality = config.get("formality") or input_data.get("formality")
    if formality:
        body["formality"] = formality
    glossary_id = config.get("glossary_id") or input_data.get("glossary_id")
    if glossary_id:
        body["glossary_id"] = glossary_id
    tag_handling = config.get("tag_handling") or input_data.get("tag_handling")
    if tag_handling:
        body["tag_handling"] = tag_handling
    async with await _client(credential_id, db) as client:
        r = await client.post("/translate", json=body)
    return _check(r)


@register_node("deepl.translate_document")
async def deepl_translate_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /document — upload and translate a document (returns document_id and document_key)."""
    file_content = config.get("file_content") or input_data.get("file_content")
    filename = config.get("filename") or input_data.get("filename", "document.txt")
    target_lang = config.get("target_lang") or input_data.get("target_lang")
    if not file_content or not target_lang:
        raise ValueError("deepl.translate_document requires 'file_content' and 'target_lang'")
    creds_data = await get_credential_data(credential_id, db)
    api_key = creds_data.get("api_key")
    is_pro = creds_data.get("pro", False)
    if isinstance(is_pro, str):
        is_pro = is_pro.lower() in ("true", "1", "yes")
    base_url = "https://api.deepl.com/v2" if is_pro else "https://api-free.deepl.com/v2"
    if isinstance(file_content, str):
        import base64
        file_bytes = base64.b64decode(file_content)
    else:
        file_bytes = file_content
    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        timeout=120.0,
    ) as client:
        r = await client.post(
            "/document",
            data={"target_lang": target_lang.upper()},
            files={"file": (filename, file_bytes)},
        )
    return _check(r)


@register_node("deepl.get_usage")
async def deepl_get_usage(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /usage — get usage statistics for the current billing period."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/usage")
    return _check(r)


@register_node("deepl.list_languages")
async def deepl_list_languages(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /languages — list supported source and target languages."""
    params: dict = {}
    type_ = config.get("type") or input_data.get("type")
    if type_:
        params["type"] = type_
    async with await _client(credential_id, db) as client:
        r = await client.get("/languages", params=params)
    return _check(r)


@register_node("deepl.create_glossary")
async def deepl_create_glossary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """POST /glossaries — create a translation glossary."""
    name = config.get("name") or input_data.get("name")
    source_lang = config.get("source_lang") or input_data.get("source_lang")
    target_lang = config.get("target_lang") or input_data.get("target_lang")
    entries = config.get("entries") or input_data.get("entries")
    if not name or not source_lang or not target_lang or not entries:
        raise ValueError("deepl.create_glossary requires 'name', 'source_lang', 'target_lang', and 'entries'")
    # entries can be a dict or TSV string
    if isinstance(entries, dict):
        entries_str = "\n".join(f"{k}\t{v}" for k, v in entries.items())
        entries_format = "tsv"
    else:
        entries_str = entries
        entries_format = config.get("entries_format") or input_data.get("entries_format", "tsv")
    body = {
        "name": name,
        "source_lang": source_lang.lower(),
        "target_lang": target_lang.lower(),
        "entries": entries_str,
        "entries_format": entries_format,
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/glossaries", json=body)
    return _check(r)


@register_node("deepl.list_glossaries")
async def deepl_list_glossaries(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /glossaries — list all glossaries."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/glossaries")
    return _check(r)


@register_node("deepl.get_glossary")
async def deepl_get_glossary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /glossaries/{id} — get a specific glossary."""
    glossary_id = config.get("glossary_id") or input_data.get("glossary_id")
    if not glossary_id:
        raise ValueError("deepl.get_glossary requires 'glossary_id'")
    async with await _client(credential_id, db) as client:
        r = await client.get(f"/glossaries/{glossary_id}")
    return _check(r)


@register_node("deepl.delete_glossary")
async def deepl_delete_glossary(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """DELETE /glossaries/{id} — delete a glossary."""
    glossary_id = config.get("glossary_id") or input_data.get("glossary_id")
    if not glossary_id:
        raise ValueError("deepl.delete_glossary requires 'glossary_id'")
    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/glossaries/{glossary_id}")
    if r.status_code == 204:
        return {"ok": True, "glossary_id": glossary_id}
    return _check(r)


@register_node("deepl.list_glossary_language_pairs")
async def deepl_list_glossary_language_pairs(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """GET /glossary-language-pairs — list supported glossary language pairs."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/glossary-language-pairs")
    return _check(r)


async def test_connection(credential_id: str, db) -> dict:
    """Test DeepL connection by fetching usage statistics."""
    async with await _client(credential_id, db) as client:
        r = await client.get("/usage")
    _check(r)
    return {"ok": True}
