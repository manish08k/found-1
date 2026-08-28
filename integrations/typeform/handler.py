"""
Typeform integration — forms, responses, webhooks.
Nodes: typeform.list_forms, typeform.get_form, typeform.get_responses,
       typeform.create_webhook, typeform.delete_webhook
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

TYPEFORM_API = "https://api.typeform.com"


def _headers(config):
    token = config.get("access_token") or getattr(settings, "TYPEFORM_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("typeform nodes require TYPEFORM_ACCESS_TOKEN or 'access_token'")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("typeform.list_forms")
async def typeform_list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    page_size = min(int(merged.get("page_size", 10)), 200)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{TYPEFORM_API}/forms",
            params={"page_size": page_size},
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    return {"forms": [{"id": f["id"], "title": f.get("title"), "type": f.get("type")} for f in items],
            "count": data.get("total_items", len(items))}


@register_node("typeform.get_form")
async def typeform_get_form(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("typeform.get_form requires 'form_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{TYPEFORM_API}/forms/{form_id}", headers=_headers(merged))
        r.raise_for_status()
        data = r.json()

    fields = [{"id": f["id"], "type": f["type"], "title": f.get("title")} for f in data.get("fields", [])]
    return {"id": data["id"], "title": data.get("title"), "fields": fields}


@register_node("typeform.get_responses")
async def typeform_get_responses(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    form_id = merged.get("form_id")
    if not form_id:
        raise ValueError("typeform.get_responses requires 'form_id'")

    page_size = min(int(merged.get("page_size", 25)), 1000)
    params = {"page_size": page_size}
    if merged.get("since"):
        params["since"] = merged["since"]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{TYPEFORM_API}/forms/{form_id}/responses",
            params=params,
            headers=_headers(merged),
        )
        r.raise_for_status()
        data = r.json()

    responses = []
    for resp in data.get("items", []):
        answers = {}
        for answer in resp.get("answers", []):
            field_id = answer.get("field", {}).get("id", "")
            val = (answer.get("text") or answer.get("choice", {}).get("label")
                   or answer.get("number") or answer.get("boolean") or answer.get("email"))
            answers[field_id] = val
        responses.append({
            "response_id": resp.get("response_id"),
            "submitted_at": resp.get("submitted_at"),
            "answers": answers,
        })

    return {"responses": responses, "total": data.get("total_items", len(responses))}


@register_node("typeform.create_webhook")
async def typeform_create_webhook(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    form_id = merged.get("form_id")
    url = merged.get("url")
    tag = merged.get("tag", "autoflow")

    if not form_id or not url:
        raise ValueError("typeform.create_webhook requires 'form_id' and 'url'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.put(
            f"{TYPEFORM_API}/forms/{form_id}/webhooks/{tag}",
            json={"url": url, "enabled": True},
            headers=_headers(merged),
        )
        r.raise_for_status()
        return {"webhook": r.json(), "ok": True}
