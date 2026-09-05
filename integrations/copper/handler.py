"""
Copper CRM integration.

Provides people, companies, and opportunities management via the
Copper Developer API v1.

Credential fields:
  - api_key    : Copper API key
  - user_email : The email of the Copper user associated with the API key

Base URL: https://api.copper.com/developer_api/v1/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.copper.com/developer_api/v1"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    user_email = creds.get("user_email")
    if not api_key:
        raise ValueError("Copper credential missing 'api_key'")
    if not user_email:
        raise ValueError("Copper credential missing 'user_email'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "X-PW-AccessToken": api_key,
            "X-PW-Application": "developer_api",
            "X-PW-UserEmail": user_email,
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
        raise ValueError(f"Copper API error {r.status_code}: {detail}")


@register_node("copper.list_people")
async def copper_list_people(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search / list people (contacts) in Copper CRM.

    Config:
      - name       : Optional name filter
      - email      : Optional email filter
      - page_size  : Results per page (default 20, max 200)
      - page_number: 1-based page number (default 1)
    """
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 20)), 200)
    page_number = int(config.get("page_number") or input_data.get("page_number", 1))

    search: dict = {"page_size": page_size, "page_number": page_number}
    name = config.get("name") or input_data.get("name")
    email = config.get("email") or input_data.get("email")
    if name:
        search["name"] = name
    if email:
        search["emails"] = [{"email": email, "category": "work"}]

    async with await _client(credential_id, db) as client:
        r = await client.post("/people/search", json=search)
        _raise_for_status(r)
        data = r.json()

    return {"people": data, "count": len(data)}


@register_node("copper.create_person")
async def copper_create_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new person (contact) in Copper CRM.

    Config:
      - name       : Full name (required)
      - email      : Email address
      - phone      : Phone number
      - company_id : ID of the associated company
      - title      : Job title
    """
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("copper.create_person requires 'name'")

    payload: dict = {"name": name}

    email = config.get("email") or input_data.get("email")
    if email:
        payload["emails"] = [{"email": email, "category": "work"}]

    phone = config.get("phone") or input_data.get("phone")
    if phone:
        payload["phone_numbers"] = [{"number": phone, "category": "work"}]

    company_id = config.get("company_id") or input_data.get("company_id")
    if company_id:
        payload["company_id"] = int(company_id)

    title = config.get("title") or input_data.get("title")
    if title:
        payload["title"] = title

    async with await _client(credential_id, db) as client:
        r = await client.post("/people", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"person": data, "person_id": data.get("id")}


@register_node("copper.get_person")
async def copper_get_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get a person by ID from Copper CRM.

    Config:
      - person_id : The Copper person ID (required)
    """
    person_id = config.get("person_id") or input_data.get("person_id")
    if not person_id:
        raise ValueError("copper.get_person requires 'person_id'")

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/people/{person_id}")
        _raise_for_status(r)
        data = r.json()

    return {"person": data}


@register_node("copper.create_opportunity")
async def copper_create_opportunity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create a new opportunity (deal) in Copper CRM.

    Config:
      - name        : Opportunity name (required)
      - company_id  : ID of the associated company
      - company_name: Name of associated company (used if company_id not provided)
      - monetary_value : Deal value (number)
      - pipeline_id : ID of the pipeline
      - pipeline_stage_id : ID of the stage
      - close_date  : Expected close date as a Unix timestamp
      - status      : 'Open', 'Won', 'Lost', 'Abandoned' (default: 'Open')
    """
    name = config.get("name") or input_data.get("name")
    if not name:
        raise ValueError("copper.create_opportunity requires 'name'")

    payload: dict = {"name": name}

    company_id = config.get("company_id") or input_data.get("company_id")
    company_name = config.get("company_name") or input_data.get("company_name")
    if company_id:
        payload["company_id"] = int(company_id)
    elif company_name:
        payload["company_name"] = company_name

    monetary_value = config.get("monetary_value") or input_data.get("monetary_value")
    if monetary_value is not None:
        payload["monetary_value"] = float(monetary_value)

    pipeline_id = config.get("pipeline_id") or input_data.get("pipeline_id")
    if pipeline_id:
        payload["pipeline_id"] = int(pipeline_id)

    pipeline_stage_id = config.get("pipeline_stage_id") or input_data.get("pipeline_stage_id")
    if pipeline_stage_id:
        payload["pipeline_stage_id"] = int(pipeline_stage_id)

    close_date = config.get("close_date") or input_data.get("close_date")
    if close_date:
        payload["close_date"] = int(close_date)

    status = config.get("status") or input_data.get("status", "Open")
    payload["status"] = status

    async with await _client(credential_id, db) as client:
        r = await client.post("/opportunities", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {"opportunity": data, "opportunity_id": data.get("id")}


@register_node("copper.list_companies")
async def copper_list_companies(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search / list companies in Copper CRM.

    Config:
      - name       : Optional name filter
      - page_size  : Results per page (default 20, max 200)
      - page_number: 1-based page number (default 1)
    """
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 20)), 200)
    page_number = int(config.get("page_number") or input_data.get("page_number", 1))

    search: dict = {"page_size": page_size, "page_number": page_number}
    name = config.get("name") or input_data.get("name")
    if name:
        search["name"] = name

    async with await _client(credential_id, db) as client:
        r = await client.post("/companies/search", json=search)
        _raise_for_status(r)
        data = r.json()

    return {"companies": data, "count": len(data)}


@register_node("copper.list_opportunities")
async def copper_list_opportunities(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Search / list opportunities in Copper CRM.

    Config:
      - name        : Optional name filter
      - status      : Filter by status ('Open', 'Won', 'Lost', 'Abandoned')
      - page_size   : Results per page (default 20, max 200)
      - page_number : 1-based page number (default 1)
    """
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 20)), 200)
    page_number = int(config.get("page_number") or input_data.get("page_number", 1))

    search: dict = {"page_size": page_size, "page_number": page_number}
    name = config.get("name") or input_data.get("name")
    if name:
        search["name"] = name
    statuses = config.get("statuses") or input_data.get("statuses")
    if statuses:
        search["statuses"] = statuses if isinstance(statuses, list) else [statuses]

    async with await _client(credential_id, db) as client:
        r = await client.post("/opportunities/search", json=search)
        _raise_for_status(r)
        data = r.json()

    return {"opportunities": data, "count": len(data)}
