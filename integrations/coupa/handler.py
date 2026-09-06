"""Coupa integration — purchase orders, suppliers, and requisitions."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _coupa_base(instance: str) -> str:
    return f"https://{instance}.coupahost.com/api"


def _coupa_headers(api_key: str) -> dict:
    return {
        "X-COUPA-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("coupa.list_purchase_orders")
async def coupa_list_purchase_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List purchase orders from Coupa.

    config:
      instance — Coupa instance name (required)
      api_key  — Coupa API key (required)
      limit    — number of records to return (optional, default 50)
      offset   — offset for pagination (optional, default 0)
      status   — filter by status e.g. "issued" (optional)
    """
    merged = {**config, **input_data}
    instance = merged.get("instance", "")
    api_key = merged.get("api_key", "")
    if not instance or not api_key:
        raise ValueError("instance and api_key are required for coupa.list_purchase_orders")

    params: dict = {"limit": merged.get("limit", 50), "offset": merged.get("offset", 0)}
    if merged.get("status"):
        params["status"] = merged["status"]

    async with httpx.AsyncClient(base_url=_coupa_base(instance), timeout=30) as client:
        r = await client.get("/purchase_orders", headers=_coupa_headers(api_key), params=params)
        r.raise_for_status()
        orders = r.json()

    log.info("coupa.list_purchase_orders", instance=instance, count=len(orders))
    return {"purchase_orders": orders, "count": len(orders)}


@register_node("coupa.get_purchase_order")
async def coupa_get_purchase_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Coupa purchase order by ID.

    config:
      instance — Coupa instance name (required)
      api_key  — Coupa API key (required)
      order_id — purchase order ID (required)
    """
    merged = {**config, **input_data}
    instance = merged.get("instance", "")
    api_key = merged.get("api_key", "")
    order_id = merged.get("order_id")
    if not instance or not api_key or not order_id:
        raise ValueError("instance, api_key, and order_id are required")

    async with httpx.AsyncClient(base_url=_coupa_base(instance), timeout=30) as client:
        r = await client.get(f"/purchase_orders/{order_id}", headers=_coupa_headers(api_key))
        r.raise_for_status()
        order = r.json()

    log.info("coupa.get_purchase_order", order_id=order_id)
    return {"purchase_order": order, "order_id": order_id}


@register_node("coupa.list_suppliers")
async def coupa_list_suppliers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List suppliers from Coupa.

    config:
      instance — Coupa instance name (required)
      api_key  — Coupa API key (required)
      limit    — number of records to return (optional, default 50)
      offset   — offset for pagination (optional, default 0)
    """
    merged = {**config, **input_data}
    instance = merged.get("instance", "")
    api_key = merged.get("api_key", "")
    if not instance or not api_key:
        raise ValueError("instance and api_key are required")

    params = {"limit": merged.get("limit", 50), "offset": merged.get("offset", 0)}

    async with httpx.AsyncClient(base_url=_coupa_base(instance), timeout=30) as client:
        r = await client.get("/suppliers", headers=_coupa_headers(api_key), params=params)
        r.raise_for_status()
        suppliers = r.json()

    log.info("coupa.list_suppliers", instance=instance, count=len(suppliers))
    return {"suppliers": suppliers, "count": len(suppliers)}


@register_node("coupa.get_supplier")
async def coupa_get_supplier(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a single Coupa supplier by ID.

    config:
      instance    — Coupa instance name (required)
      api_key     — Coupa API key (required)
      supplier_id — supplier ID (required)
    """
    merged = {**config, **input_data}
    instance = merged.get("instance", "")
    api_key = merged.get("api_key", "")
    supplier_id = merged.get("supplier_id")
    if not instance or not api_key or not supplier_id:
        raise ValueError("instance, api_key, and supplier_id are required")

    async with httpx.AsyncClient(base_url=_coupa_base(instance), timeout=30) as client:
        r = await client.get(f"/suppliers/{supplier_id}", headers=_coupa_headers(api_key))
        r.raise_for_status()
        supplier = r.json()

    log.info("coupa.get_supplier", supplier_id=supplier_id)
    return {"supplier": supplier, "supplier_id": supplier_id}


@register_node("coupa.create_requisition")
async def coupa_create_requisition(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a purchase requisition in Coupa.

    config:
      instance     — Coupa instance name (required)
      api_key      — Coupa API key (required)
      ship_to_user — ship-to user dict with id field (required)
      requisition_lines — list of line item dicts (required)
      description  — requisition description (optional)
    """
    merged = {**config, **input_data}
    instance = merged.get("instance", "")
    api_key = merged.get("api_key", "")
    if not instance or not api_key:
        raise ValueError("instance and api_key are required")

    payload: dict = {}
    if merged.get("ship_to_user"):
        payload["ship-to-user"] = merged["ship_to_user"]
    if merged.get("description"):
        payload["description"] = merged["description"]
    if merged.get("requisition_lines"):
        payload["requisition-lines"] = {"requisition-line": merged["requisition_lines"]}

    async with httpx.AsyncClient(base_url=_coupa_base(instance), timeout=30) as client:
        r = await client.post("/requisitions", headers=_coupa_headers(api_key), json=payload)
        r.raise_for_status()
        requisition = r.json()

    requisition_id = requisition.get("id")
    log.info("coupa.create_requisition", requisition_id=requisition_id)
    return {"requisition": requisition, "requisition_id": requisition_id}
