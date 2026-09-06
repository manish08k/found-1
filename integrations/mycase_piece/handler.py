"""MyCase legal practice management — handler for mycase integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.mycase.com/v1"


@register_node("mycase.list_contacts")
async def mycase_list_contacts(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List contacts.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/contacts", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("mycase.list_contacts")
    return {"data": data}

@register_node("mycase.create_contact")
async def mycase_create_contact(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a contact.

    config/input_data:
      api_key — API key or token (required)
      first_name — (required)
      last_name — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    first_name = merged.get("first_name") or ""
    last_name = merged.get("last_name") or ""
    if not first_name or not last_name:
        raise ValueError("first_name, last_name required for mycase.create_contact")
    payload = {"first_name": first_name, "last_name": last_name}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/contacts", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("mycase.create_contact")
    return {"data": data}

@register_node("mycase.list_cases")
async def mycase_list_cases(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List cases.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/cases", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("mycase.list_cases")
    return {"data": data}

@register_node("mycase.create_case")
async def mycase_create_case(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a case.

    config/input_data:
      api_key — API key or token (required)
      name — (required)
      case_type — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    name = merged.get("name") or ""
    case_type = merged.get("case_type") or ""
    if not name or not case_type:
        raise ValueError("name, case_type required for mycase.create_case")
    payload = {"name": name, "case_type": case_type}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/cases", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("mycase.create_case")
    return {"data": data}
