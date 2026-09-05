"""Folk CRM integration — groups, contacts, and group membership."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

FOLK_BASE = "https://api.folk.app/v2"


@register_node("folk.list_groups")
async def folk_list_groups(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all groups in Folk CRM.

    config/input_data:
      api_key — Folk API key (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{FOLK_BASE}/groups"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    groups = data.get("data", data) if isinstance(data, dict) else data
    log.info("folk.list_groups", count=len(groups) if isinstance(groups, list) else None)
    return {"groups": groups}


@register_node("folk.list_contacts")
async def folk_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts (people) in Folk CRM, optionally filtered by group.

    config/input_data:
      api_key  — Folk API key (required)
      group_id — group ID to filter by (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    group_id = merged.get("group_id")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{FOLK_BASE}/people"
    params: dict = {}
    if group_id:
        params["groupId"] = group_id

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

    contacts = data.get("data", data) if isinstance(data, dict) else data
    log.info("folk.list_contacts", group_id=group_id, count=len(contacts) if isinstance(contacts, list) else None)
    return {"contacts": contacts}


@register_node("folk.create_contact")
async def folk_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new contact (person) in Folk CRM.

    config/input_data:
      api_key    — Folk API key (required)
      first_name — first name (required)
      last_name  — last name
      email      — email address
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    fn = merged.get("first_name") or ""
    ln = merged.get("last_name") or ""
    email = merged.get("email") or ""

    if not fn:
        raise ValueError("first_name is required for folk.create_contact")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{FOLK_BASE}/people"
    payload: dict = {"name": {"firstName": fn, "lastName": ln}}
    if email:
        payload["email"] = email

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    contact = data.get("data", data) if isinstance(data, dict) else data
    log.info("folk.create_contact", first_name=fn, last_name=ln)
    return {"contact": contact}


@register_node("folk.add_to_group")
async def folk_add_to_group(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a Folk contact to a group.

    config/input_data:
      api_key   — Folk API key (required)
      person_id — person/contact ID (required)
      group_id  — group ID to add the person to (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    person_id = merged.get("person_id") or ""
    group_id = merged.get("group_id") or ""

    if not person_id:
        raise ValueError("person_id is required for folk.add_to_group")
    if not group_id:
        raise ValueError("group_id is required for folk.add_to_group")

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{FOLK_BASE}/people/{person_id}/groups"
    payload = {"groupIds": [group_id]}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("folk.add_to_group", person_id=person_id, group_id=group_id)
    return {"result": data}
