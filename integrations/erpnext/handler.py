"""
ERPNext open-source ERP integration.

Provides full CRUD over any ERPNext DocType via the REST API.

Credential fields:
  - base_url  : ERPNext instance URL, e.g. https://mycompany.erpnext.com
  - username  : ERPNext username (usually an email)
  - password  : ERPNext password

Authentication: session-based cookie obtained via /api/method/login.
The token is passed in subsequent requests using the `Authorization` header
(api_key + api_secret) if available, otherwise a fresh login is attempted.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ERPNext API error {r.status_code}: {detail}")


async def _client(credential_id: str, db) -> tuple[httpx.AsyncClient, str]:
    """
    Return an authenticated AsyncClient and the base resource URL.

    Supports two auth modes:
      1. api_key + api_secret  →  Token <api_key>:<api_secret> header
      2. username + password   →  Login via /api/method/login then cookie
    """
    creds = await get_credential_data(credential_id, db)
    base_url = creds.get("base_url", "").rstrip("/")
    if not base_url:
        raise ValueError("ERPNext credential missing 'base_url'")

    api_key = creds.get("api_key", "").strip()
    api_secret = creds.get("api_secret", "").strip()
    username = creds.get("username", "").strip()
    password = creds.get("password", "").strip()

    headers: dict = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if api_key and api_secret:
        headers["Authorization"] = f"token {api_key}:{api_secret}"
        client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0)
    elif username and password:
        # Session login
        client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30.0)
        r = await client.post(
            "/api/method/login",
            json={"usr": username, "pwd": password},
        )
        _raise_for_status(r)
    else:
        raise ValueError("ERPNext credential requires 'api_key'+'api_secret' or 'username'+'password'")

    return client, f"{base_url}/api/resource"


@register_node("erpnext.create_document")
async def create_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Create a new ERPNext document (any DocType).

    Config / input keys:
      - doctype (str)  : Required. ERPNext DocType, e.g. "Customer", "Sales Order".
      - data    (dict) : Required. Field-value pairs for the new document.

    Returns:
      { "doctype": str, "name": str, "document": dict }
    """
    doctype = config.get("doctype") or input_data.get("doctype")
    data = config.get("data") or input_data.get("data", {})

    if not doctype:
        raise ValueError("erpnext.create_document requires 'doctype'")
    if not data:
        raise ValueError("erpnext.create_document requires 'data'")

    payload = {"doctype": doctype, **data}

    log.info("erpnext.create_document", doctype=doctype)

    client, resource_base = await _client(credential_id, db)
    async with client:
        r = await client.post(f"{resource_base}/{doctype}", json=payload)
        _raise_for_status(r)
        result = r.json()

    document = result.get("data", result)
    return {
        "doctype": doctype,
        "name": document.get("name"),
        "document": document,
    }


@register_node("erpnext.get_document")
async def get_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Retrieve a single ERPNext document by name/ID.

    Config / input keys:
      - doctype (str)  : Required. ERPNext DocType.
      - name    (str)  : Required. Document name/ID, e.g. "CUST-00001".

    Returns:
      { "doctype": str, "name": str, "document": dict }
    """
    doctype = config.get("doctype") or input_data.get("doctype")
    name = config.get("name") or input_data.get("name")

    if not doctype:
        raise ValueError("erpnext.get_document requires 'doctype'")
    if not name:
        raise ValueError("erpnext.get_document requires 'name'")

    log.info("erpnext.get_document", doctype=doctype, name=name)

    client, resource_base = await _client(credential_id, db)
    async with client:
        r = await client.get(f"{resource_base}/{doctype}/{name}")
        _raise_for_status(r)
        result = r.json()

    document = result.get("data", result)
    return {
        "doctype": doctype,
        "name": name,
        "document": document,
    }


@register_node("erpnext.list_documents")
async def list_documents(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    List documents of a given ERPNext DocType with optional filters.

    Config / input keys:
      - doctype  (str)        : Required. DocType to list.
      - filters  (list|dict)  : ERPNext filter list, e.g.
                                [["Customer", "territory", "=", "India"]].
      - fields   (list[str])  : Fields to return. Default ["name"].
      - limit    (int)        : Max records (1-500). Default 20.
      - order_by (str)        : ORDER BY clause, e.g. "creation desc".

    Returns:
      { "doctype": str, "documents": [...], "count": int }
    """
    doctype = config.get("doctype") or input_data.get("doctype")
    if not doctype:
        raise ValueError("erpnext.list_documents requires 'doctype'")

    filters = config.get("filters") or input_data.get("filters", [])
    fields = config.get("fields") or input_data.get("fields", ["name"])
    limit = min(int(config.get("limit") or input_data.get("limit", 20)), 500)
    order_by = config.get("order_by") or input_data.get("order_by", "creation desc")

    import json as _json

    params: dict = {
        "fields": _json.dumps(fields) if isinstance(fields, list) else fields,
        "limit_page_length": limit,
        "order_by": order_by,
    }
    if filters:
        params["filters"] = _json.dumps(filters) if isinstance(filters, list) else filters

    log.info("erpnext.list_documents", doctype=doctype, limit=limit)

    client, resource_base = await _client(credential_id, db)
    async with client:
        r = await client.get(f"{resource_base}/{doctype}", params=params)
        _raise_for_status(r)
        result = r.json()

    documents = result.get("data", result if isinstance(result, list) else [])
    return {
        "doctype": doctype,
        "documents": documents,
        "count": len(documents),
    }


@register_node("erpnext.update_document")
async def update_document(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Update fields on an existing ERPNext document.

    Config / input keys:
      - doctype (str)  : Required. DocType.
      - name    (str)  : Required. Document name/ID.
      - data    (dict) : Required. Fields to update.

    Returns:
      { "doctype": str, "name": str, "document": dict, "updated": bool }
    """
    doctype = config.get("doctype") or input_data.get("doctype")
    name = config.get("name") or input_data.get("name")
    data = config.get("data") or input_data.get("data", {})

    if not doctype:
        raise ValueError("erpnext.update_document requires 'doctype'")
    if not name:
        raise ValueError("erpnext.update_document requires 'name'")
    if not data:
        raise ValueError("erpnext.update_document requires 'data'")

    log.info("erpnext.update_document", doctype=doctype, name=name)

    client, resource_base = await _client(credential_id, db)
    async with client:
        r = await client.put(f"{resource_base}/{doctype}/{name}", json=data)
        _raise_for_status(r)
        result = r.json()

    document = result.get("data", result)
    return {
        "doctype": doctype,
        "name": name,
        "document": document,
        "updated": True,
    }
