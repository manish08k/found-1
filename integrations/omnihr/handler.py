"""OmniHR human resources platform — handler for omnihr integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = "https://api.omnihr.co/v1"


@register_node("omnihr.list_employees")
async def omnihr_list_employees(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List employees.

    config/input_data:
      api_key — API key or token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/employees", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("omnihr.list_employees")
    return {"data": data}

@register_node("omnihr.get_employee")
async def omnihr_get_employee(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get employee details.

    config/input_data:
      api_key — API key or token (required)
      employee_id — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    employee_id = merged.get("employee_id") or ""
    if not employee_id:
        raise ValueError("employee_id required for omnihr.get_employee")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}/employees/{employee_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
    log.info("omnihr.get_employee")
    return {"data": data}

@register_node("omnihr.create_employee")
async def omnihr_create_employee(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create an employee record.

    config/input_data:
      api_key — API key or token (required)
      first_name — (required)
      last_name — (required)
      email — (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or merged.get("api_token") or ""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    first_name = merged.get("first_name") or ""
    last_name = merged.get("last_name") or ""
    email = merged.get("email") or ""
    if not first_name or not last_name or not email:
        raise ValueError("first_name, last_name, email required for omnihr.create_employee")
    payload = {"first_name": first_name, "last_name": last_name, "email": email}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}/employees", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    log.info("omnihr.create_employee")
    return {"data": data}
