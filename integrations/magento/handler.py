"""
Magento e-commerce integration.

Provides product listing, order management, and customer listing via the Magento REST API V1.
Authenticates using admin username + password to obtain an OAuth token.

Credential fields:
  - username : Magento admin username
  - password : Magento admin password
  - base_url : Magento store base URL (e.g. https://store.example.com)
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _get_token(base_url: str, username: str, password: str) -> str:
    """Authenticate with Magento and return an admin token."""
    token_url = f"{base_url}/rest/V1/integration/admin/token"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(token_url, json={"username": username, "password": password})
        if r.status_code >= 300:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise ValueError(f"Magento authentication failed {r.status_code}: {detail}")
        token = r.json()
        if not isinstance(token, str):
            raise ValueError(f"Unexpected Magento token response: {token}")
        return token


async def _client(credential_id: str, db) -> tuple:
    """Return (httpx.AsyncClient, base_rest_url) for Magento REST API calls."""
    creds = await get_credential_data(credential_id, db)
    username = creds.get("username")
    password = creds.get("password")
    base_url = creds.get("base_url", "").rstrip("/")

    if not username:
        raise ValueError("Magento credential missing 'username'")
    if not password:
        raise ValueError("Magento credential missing 'password'")
    if not base_url:
        raise ValueError("Magento credential missing 'base_url'")

    token = await _get_token(base_url, username, password)
    rest_base = f"{base_url}/rest/V1"
    client = httpx.AsyncClient(
        base_url=rest_base,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
    return client, rest_base


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Magento API error {r.status_code}: {detail}")


@register_node("magento.list_products")
async def magento_list_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List products from a Magento store."""
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 20)), 300)
    current_page = int(config.get("current_page") or input_data.get("current_page", 1))
    search_term = config.get("search_term") or input_data.get("search_term")

    params: dict = {
        "searchCriteria[pageSize]": page_size,
        "searchCriteria[currentPage]": current_page,
    }
    if search_term:
        params["searchCriteria[filterGroups][0][filters][0][field]"] = "name"
        params["searchCriteria[filterGroups][0][filters][0][value]"] = f"%{search_term}%"
        params["searchCriteria[filterGroups][0][filters][0][conditionType]"] = "like"

    log.info("magento.list_products", page_size=page_size, current_page=current_page)
    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.get("/products", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "products": data.get("items", []),
        "total_count": data.get("total_count", 0),
        "page": current_page,
    }


@register_node("magento.create_order")
async def magento_create_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create an order in Magento."""
    order_data = config.get("order") or input_data.get("order")
    if not order_data:
        raise ValueError("magento.create_order requires 'order' dict with order payload")

    log.info("magento.create_order")
    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.post("/orders", json={"entity": order_data})
        _raise_for_status(r)
        order = r.json()

    return {"order": order, "order_id": order.get("entity_id")}


@register_node("magento.get_order")
async def magento_get_order(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Get a specific order from Magento by order ID."""
    order_id = config.get("order_id") or input_data.get("order_id")
    if not order_id:
        raise ValueError("magento.get_order requires 'order_id'")

    log.info("magento.get_order", order_id=order_id)
    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.get(f"/orders/{order_id}")
        _raise_for_status(r)
        order = r.json()

    return {"order": order}


@register_node("magento.list_customers")
async def magento_list_customers(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List customers from a Magento store."""
    page_size = min(int(config.get("page_size") or input_data.get("page_size", 20)), 300)
    current_page = int(config.get("current_page") or input_data.get("current_page", 1))
    email = config.get("email") or input_data.get("email")

    params: dict = {
        "searchCriteria[pageSize]": page_size,
        "searchCriteria[currentPage]": current_page,
    }
    if email:
        params["searchCriteria[filterGroups][0][filters][0][field]"] = "email"
        params["searchCriteria[filterGroups][0][filters][0][value]"] = email
        params["searchCriteria[filterGroups][0][filters][0][conditionType]"] = "eq"

    log.info("magento.list_customers", page_size=page_size, current_page=current_page)
    client, _ = await _client(credential_id, db)
    async with client:
        r = await client.get("/customers/search", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "customers": data.get("items", []),
        "total_count": data.get("total_count", 0),
        "page": current_page,
    }
