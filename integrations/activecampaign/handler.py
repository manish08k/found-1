"""
ActiveCampaign CRM & Email Marketing integration.

Provides contact management, tagging, list subscriptions, deal tracking,
and note creation via the ActiveCampaign API v3.

Credential fields:
  - api_url  : Your account base URL, e.g. https://youraccountname.api-us1.com
  - api_key  : ActiveCampaign API key (found in Account Settings > Developer)

Auth: Api-Token header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

try:
    from core.ssrf_guard import assert_safe_url
    _SSRF_AVAILABLE = True
except Exception:
    _SSRF_AVAILABLE = False

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_url = creds.get("api_url", "").rstrip("/")
    api_key = creds.get("api_key")
    if not api_url:
        raise ValueError("ActiveCampaign credential missing 'api_url'")
    if not api_key:
        raise ValueError("ActiveCampaign credential missing 'api_key'")
    if _SSRF_AVAILABLE:
        assert_safe_url(api_url)
    return httpx.AsyncClient(
        base_url=f"{api_url}/api/3",
        headers={"Api-Token": api_key, "Content-Type": "application/json"},
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ActiveCampaign API error {r.status_code}: {detail}")


@register_node("activecampaign.create_contact")
async def ac_create_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email = config.get("email") or input_data.get("email")
    first_name = config.get("first_name") or input_data.get("first_name", "")
    last_name = config.get("last_name") or input_data.get("last_name", "")
    phone = config.get("phone") or input_data.get("phone", "")
    tags_raw = config.get("tags") or input_data.get("tags", "")

    if not email:
        raise ValueError("activecampaign.create_contact requires 'email'")

    contact_payload = {"email": email}
    if first_name:
        contact_payload["firstName"] = first_name
    if last_name:
        contact_payload["lastName"] = last_name
    if phone:
        contact_payload["phone"] = phone

    async with await _client(credential_id, db) as client:
        r = await client.post("/contacts", json={"contact": contact_payload})
        _raise_for_status(r)
        data = r.json()
        contact = data.get("contact", {})
        contact_id = contact.get("id")

        # Auto-add tags if provided
        if tags_raw and contact_id:
            tag_names = [t.strip() for t in str(tags_raw).split(",") if t.strip()]
            for tag_name in tag_names:
                # Look up or create tag
                tag_r = await client.get("/tags", params={"search": tag_name})
                _raise_for_status(tag_r)
                tag_data = tag_r.json()
                existing_tags = [t for t in tag_data.get("tags", []) if t.get("tag") == tag_name]
                if existing_tags:
                    tag_id = existing_tags[0]["id"]
                else:
                    new_tag_r = await client.post("/tags", json={"tag": {"tag": tag_name, "tagType": "contact"}})
                    _raise_for_status(new_tag_r)
                    tag_id = new_tag_r.json().get("tag", {}).get("id")
                if tag_id:
                    await client.post("/contactTags", json={"contactTag": {"contact": contact_id, "tag": tag_id}})

    return {"contact": contact, "contact_id": contact_id}


@register_node("activecampaign.get_contact")
async def ac_get_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if not contact_id:
        raise ValueError("activecampaign.get_contact requires 'contact_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/contacts/{contact_id}")
        _raise_for_status(r)
        data = r.json()

    return {"contact": data.get("contact", {})}


@register_node("activecampaign.update_contact")
async def ac_update_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if not contact_id:
        raise ValueError("activecampaign.update_contact requires 'contact_id'")

    fields = {}
    for key in ("email", "first_name", "last_name", "phone"):
        val = config.get(key) or input_data.get(key)
        if val:
            # Map snake_case to camelCase for AC API
            ac_key = {"first_name": "firstName", "last_name": "lastName"}.get(key, key)
            fields[ac_key] = val

    async with await _client(credential_id, db) as client:
        r = await client.put(f"/contacts/{contact_id}", json={"contact": fields})
        _raise_for_status(r)
        data = r.json()

    return {"contact": data.get("contact", {})}


@register_node("activecampaign.list_contacts")
async def ac_list_contacts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    limit = min(int(config.get("limit") or input_data.get("limit", 20)), 100)
    offset = int(config.get("offset") or input_data.get("offset", 0))
    email_filter = config.get("email") or input_data.get("email")

    params: dict = {"limit": limit, "offset": offset}
    if email_filter:
        params["email"] = email_filter

    async with await _client(credential_id, db) as client:
        r = await client.get("/contacts", params=params)
        _raise_for_status(r)
        data = r.json()

    return {"contacts": data.get("contacts", []), "meta": data.get("meta", {})}


@register_node("activecampaign.delete_contact")
async def ac_delete_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if not contact_id:
        raise ValueError("activecampaign.delete_contact requires 'contact_id'")

    async with await _client(credential_id, db) as client:
        r = await client.delete(f"/contacts/{contact_id}")
        _raise_for_status(r)

    return {"deleted": True, "contact_id": contact_id}


@register_node("activecampaign.add_tag")
async def ac_add_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    tag_name = config.get("tag") or input_data.get("tag")
    if not contact_id or not tag_name:
        raise ValueError("activecampaign.add_tag requires 'contact_id' and 'tag'")

    async with await _client(credential_id, db) as client:
        # Look up or create tag
        tag_r = await client.get("/tags", params={"search": tag_name})
        _raise_for_status(tag_r)
        tag_data = tag_r.json()
        existing_tags = [t for t in tag_data.get("tags", []) if t.get("tag") == tag_name]
        if existing_tags:
            tag_id = existing_tags[0]["id"]
        else:
            new_tag_r = await client.post("/tags", json={"tag": {"tag": tag_name, "tagType": "contact"}})
            _raise_for_status(new_tag_r)
            tag_id = new_tag_r.json().get("tag", {}).get("id")

        assoc_r = await client.post("/contactTags", json={"contactTag": {"contact": str(contact_id), "tag": str(tag_id)}})
        _raise_for_status(assoc_r)
        contact_tag = assoc_r.json().get("contactTag", {})

    return {"contact_tag": contact_tag, "tag_id": tag_id}


@register_node("activecampaign.remove_tag")
async def ac_remove_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    tag_name = config.get("tag") or input_data.get("tag")
    if not contact_id or not tag_name:
        raise ValueError("activecampaign.remove_tag requires 'contact_id' and 'tag'")

    async with await _client(credential_id, db) as client:
        # Find the tag id
        tag_r = await client.get("/tags", params={"search": tag_name})
        _raise_for_status(tag_r)
        tag_data = tag_r.json()
        existing_tags = [t for t in tag_data.get("tags", []) if t.get("tag") == tag_name]
        if not existing_tags:
            return {"removed": False, "reason": "tag not found"}
        tag_id = existing_tags[0]["id"]

        # Find the contactTag association id
        ct_r = await client.get("/contactTags", params={"contact": contact_id, "tag": tag_id})
        _raise_for_status(ct_r)
        contact_tags = ct_r.json().get("contactTags", [])
        if not contact_tags:
            return {"removed": False, "reason": "association not found"}

        contact_tag_id = contact_tags[0]["id"]
        del_r = await client.delete(f"/contactTags/{contact_tag_id}")
        _raise_for_status(del_r)

    return {"removed": True, "contact_tag_id": contact_tag_id}


@register_node("activecampaign.add_to_list")
async def ac_add_to_list(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    list_id = config.get("list_id") or input_data.get("list_id")
    status = int(config.get("status") or input_data.get("status", 1))
    if not contact_id or not list_id:
        raise ValueError("activecampaign.add_to_list requires 'contact_id' and 'list_id'")

    payload = {
        "contactList": {
            "list": str(list_id),
            "contact": str(contact_id),
            "status": status,
        }
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/contactLists", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"contact_list": data.get("contactList", {})}


@register_node("activecampaign.send_email")
async def ac_send_email(config: dict, input_data: dict, credential_id: str, db) -> dict:
    email_id = config.get("email_id") or input_data.get("email_id")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    if not email_id or not contact_id:
        raise ValueError("activecampaign.send_email requires 'email_id' and 'contact_id'")

    payload = {
        "campaign": {
            "type": "single",
            "sdate": None,
            "sendid": str(email_id),
            "segmentid": 0,
            "bounceid": -1,
            "realcid": 0,
            "sendamount": 0,
            "totalamt": 0,
            "analytics_domains": None,
            "analytics_source": "",
            "analytics_ua": "",
            "tweet": "0",
            "fb_post": "0",
            "fb_post_initial": "0",
            "tracklinks": "all",
            "embed_images": "0",
        }
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/campaigns", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"campaign": data.get("campaign", {})}


@register_node("activecampaign.create_deal")
async def ac_create_deal(config: dict, input_data: dict, credential_id: str, db) -> dict:
    title = config.get("title") or input_data.get("title")
    value = config.get("value") or input_data.get("value", 0)
    currency = config.get("currency") or input_data.get("currency", "usd")
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")
    stage_id = config.get("stage_id") or input_data.get("stage_id")

    if not title:
        raise ValueError("activecampaign.create_deal requires 'title'")

    deal_payload: dict = {
        "title": title,
        "value": int(float(value) * 100),  # AC expects cents
        "currency": currency,
    }
    if contact_id:
        deal_payload["contact"] = str(contact_id)
    if pipeline_id:
        deal_payload["group"] = str(pipeline_id)
    if stage_id:
        deal_payload["stage"] = str(stage_id)

    async with await _client(credential_id, db) as client:
        r = await client.post("/deals", json={"deal": deal_payload})
        _raise_for_status(r)
        data = r.json()

    return {"deal": data.get("deal", {})}


@register_node("activecampaign.update_deal_stage")
async def ac_update_deal_stage(config: dict, input_data: dict, credential_id: str, db) -> dict:
    deal_id = config.get("deal_id") or input_data.get("deal_id")
    stage_id = config.get("stage_id") or input_data.get("stage_id")
    if not deal_id or not stage_id:
        raise ValueError("activecampaign.update_deal_stage requires 'deal_id' and 'stage_id'")

    async with await _client(credential_id, db) as client:
        r = await client.put(f"/deals/{deal_id}", json={"deal": {"stage": str(stage_id)}})
        _raise_for_status(r)
        data = r.json()

    return {"deal": data.get("deal", {})}


@register_node("activecampaign.add_note_to_contact")
async def ac_add_note_to_contact(config: dict, input_data: dict, credential_id: str, db) -> dict:
    contact_id = config.get("contact_id") or input_data.get("contact_id")
    note_text = config.get("note") or input_data.get("note", "")
    if not contact_id:
        raise ValueError("activecampaign.add_note_to_contact requires 'contact_id'")

    payload = {
        "note": {
            "note": note_text,
            "reltype": "Subscriber",
            "relid": str(contact_id),
        }
    }
    async with await _client(credential_id, db) as client:
        r = await client.post("/notes", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"note": data.get("note", {})}


@register_node("activecampaign.get_lists")
async def ac_get_lists(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/lists", params={"limit": 100})
        _raise_for_status(r)
        data = r.json()

    return {"lists": data.get("lists", []), "meta": data.get("meta", {})}


@register_node("activecampaign.get_tags")
async def ac_get_tags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/tags", params={"limit": 100})
        _raise_for_status(r)
        data = r.json()

    return {"tags": data.get("tags", []), "meta": data.get("meta", {})}


@register_node("activecampaign.get_pipelines")
async def ac_get_pipelines(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with await _client(credential_id, db) as client:
        r = await client.get("/dealGroups", params={"limit": 100})
        _raise_for_status(r)
        data = r.json()

    return {"pipelines": data.get("dealGroups", []), "meta": data.get("meta", {})}
