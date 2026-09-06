"""Oracle Fusion Cloud ERP integration."""
import base64
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

ERP_PATH = "/fscmRestApi/resources/11.13.18.05"


def _auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


@register_node("oracle_fusion_cloud_erp.list_purchase_orders")
async def oracle_erp_list_purchase_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List purchase orders from Oracle Fusion Cloud ERP."""
    merged = {**config, **input_data}
    fusion_url = merged.get("fusion_url", "").rstrip("/")
    username = merged.get("username", "")
    password = merged.get("password", "")
    if not fusion_url:
        raise ValueError("fusion_url is required for oracle_fusion_cloud_erp.list_purchase_orders")
    if not username or not password:
        raise ValueError("username and password are required for oracle_fusion_cloud_erp.list_purchase_orders")
    params = {}
    if merged.get("limit"):
        params["limit"] = merged["limit"]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{fusion_url}{ERP_PATH}/purchaseOrders",
            headers={"Authorization": _auth_header(username, password)},
            params=params,
        )
        r.raise_for_status()
        data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    log.info("oracle_fusion_cloud_erp.list_purchase_orders", count=len(items))
    return {"purchase_orders": items, "raw": data}


@register_node("oracle_fusion_cloud_erp.create_po")
async def oracle_erp_create_po(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a purchase order in Oracle Fusion Cloud ERP."""
    merged = {**config, **input_data}
    fusion_url = merged.get("fusion_url", "").rstrip("/")
    username = merged.get("username", "")
    password = merged.get("password", "")
    if not fusion_url:
        raise ValueError("fusion_url is required for oracle_fusion_cloud_erp.create_po")
    if not username or not password:
        raise ValueError("username and password are required for oracle_fusion_cloud_erp.create_po")
    payload = {k: v for k, v in merged.items() if k not in ("fusion_url", "username", "password")}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{fusion_url}{ERP_PATH}/purchaseOrders",
            headers={"Authorization": _auth_header(username, password)},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
    log.info("oracle_fusion_cloud_erp.create_po")
    return {"purchase_order": data}


@register_node("oracle_fusion_cloud_erp.list_invoices")
async def oracle_erp_list_invoices(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List invoices from Oracle Fusion Cloud ERP."""
    merged = {**config, **input_data}
    fusion_url = merged.get("fusion_url", "").rstrip("/")
    username = merged.get("username", "")
    password = merged.get("password", "")
    if not fusion_url:
        raise ValueError("fusion_url is required for oracle_fusion_cloud_erp.list_invoices")
    if not username or not password:
        raise ValueError("username and password are required for oracle_fusion_cloud_erp.list_invoices")
    params = {}
    if merged.get("limit"):
        params["limit"] = merged["limit"]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{fusion_url}{ERP_PATH}/invoices",
            headers={"Authorization": _auth_header(username, password)},
            params=params,
        )
        r.raise_for_status()
        data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    log.info("oracle_fusion_cloud_erp.list_invoices", count=len(items))
    return {"invoices": items, "raw": data}


@register_node("oracle_fusion_cloud_erp.get_employee")
async def oracle_erp_get_employee(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get an employee from Oracle Fusion Cloud ERP."""
    merged = {**config, **input_data}
    fusion_url = merged.get("fusion_url", "").rstrip("/")
    username = merged.get("username", "")
    password = merged.get("password", "")
    employee_id = merged.get("employee_id", "")
    if not fusion_url:
        raise ValueError("fusion_url is required for oracle_fusion_cloud_erp.get_employee")
    if not username or not password:
        raise ValueError("username and password are required for oracle_fusion_cloud_erp.get_employee")
    if not employee_id:
        raise ValueError("employee_id is required for oracle_fusion_cloud_erp.get_employee")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{fusion_url}{ERP_PATH}/workers/{employee_id}",
            headers={"Authorization": _auth_header(username, password)},
        )
        r.raise_for_status()
        data = r.json()
    log.info("oracle_fusion_cloud_erp.get_employee", employee_id=employee_id)
    return {"employee": data}
