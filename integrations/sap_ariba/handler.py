"""SAP Ariba integration — purchase orders, invoices, and suppliers."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ARIBA_BASE = "https://openapi.ariba.com/api"


def _ariba_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("sap_ariba.list_purchase_orders")
async def sap_ariba_list_purchase_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List purchase orders from SAP Ariba.

    config:
      api_key      — Ariba API key (required)
      access_token — OAuth2 access token (required)
      realm        — Ariba realm name (required)
      status       — filter by status (optional)
      limit        — number of records (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    access_token = merged.get("access_token", "")
    realm = merged.get("realm", "")
    if not api_key or not access_token or not realm:
        raise ValueError("api_key, access_token, and realm are required")

    params: dict = {"realm": realm, "apiKey": api_key, "limit": merged.get("limit", 100)}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=ARIBA_BASE, timeout=30) as client:
        r = await client.get(
            "/purchase-orders/v2/prod/purchaseOrders",
            headers=_ariba_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    orders = data.get("value", data) if isinstance(data, dict) else data
    log.info("sap_ariba.list_purchase_orders", realm=realm, count=len(orders) if isinstance(orders, list) else 1)
    return {"purchase_orders": orders, "realm": realm}


@register_node("sap_ariba.get_purchase_order")
async def sap_ariba_get_purchase_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific SAP Ariba purchase order.

    config:
      api_key      — Ariba API key (required)
      access_token — OAuth2 access token (required)
      realm        — Ariba realm name (required)
      order_id     — purchase order ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    access_token = merged.get("access_token", "")
    realm = merged.get("realm", "")
    order_id = merged.get("order_id")
    if not api_key or not access_token or not realm or not order_id:
        raise ValueError("api_key, access_token, realm, and order_id are required")

    params = {"realm": realm, "apiKey": api_key}

    async with httpx.AsyncClient(base_url=ARIBA_BASE, timeout=30) as client:
        r = await client.get(
            f"/purchase-orders/v2/prod/purchaseOrders/{order_id}",
            headers=_ariba_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        order = r.json()

    log.info("sap_ariba.get_purchase_order", order_id=order_id)
    return {"purchase_order": order, "order_id": order_id}


@register_node("sap_ariba.list_invoices")
async def sap_ariba_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List invoices from SAP Ariba.

    config:
      api_key      — Ariba API key (required)
      access_token — OAuth2 access token (required)
      realm        — Ariba realm name (required)
      status       — filter by status (optional)
      limit        — number of records (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    access_token = merged.get("access_token", "")
    realm = merged.get("realm", "")
    if not api_key or not access_token or not realm:
        raise ValueError("api_key, access_token, and realm are required")

    params: dict = {"realm": realm, "apiKey": api_key, "limit": merged.get("limit", 100)}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=ARIBA_BASE, timeout=30) as client:
        r = await client.get(
            "/invoice-management/v2/prod/invoices",
            headers=_ariba_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    invoices = data.get("value", data) if isinstance(data, dict) else data
    log.info("sap_ariba.list_invoices", realm=realm, count=len(invoices) if isinstance(invoices, list) else 1)
    return {"invoices": invoices, "realm": realm}


@register_node("sap_ariba.search_suppliers")
async def sap_ariba_search_suppliers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search for suppliers in SAP Ariba Supplier Management.

    config:
      api_key      — Ariba API key (required)
      access_token — OAuth2 access token (required)
      realm        — Ariba realm name (required)
      search_term  — supplier name or keyword to search (optional)
      limit        — number of records (optional, default 100)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    access_token = merged.get("access_token", "")
    realm = merged.get("realm", "")
    if not api_key or not access_token or not realm:
        raise ValueError("api_key, access_token, and realm are required")

    params: dict = {"realm": realm, "apiKey": api_key, "limit": merged.get("limit", 100)}
    if merged.get("search_term"):
        params["searchterm"] = merged["search_term"]

    async with httpx.AsyncClient(base_url=ARIBA_BASE, timeout=30) as client:
        r = await client.get(
            "/supplier-management/v2/prod/suppliers",
            headers=_ariba_headers(access_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    suppliers = data.get("value", data) if isinstance(data, dict) else data
    log.info("sap_ariba.search_suppliers", realm=realm, count=len(suppliers) if isinstance(suppliers, list) else 1)
    return {"suppliers": suppliers, "realm": realm}
