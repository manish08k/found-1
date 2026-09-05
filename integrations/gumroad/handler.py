"""Gumroad integration — products, sales, and license verification."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

GUMROAD_BASE = "https://api.gumroad.com/v2/"


async def _gumroad_client(credential_id: str, db) -> httpx.AsyncClient:
    """Build an authenticated Gumroad AsyncClient.

    Credential fields:
      access_token — Gumroad OAuth access token
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token", "")
    return httpx.AsyncClient(
        base_url=GUMROAD_BASE,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )


@register_node("gumroad.list_products")
async def gumroad_list_products(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all products for the authenticated Gumroad user.

    Returns full product details including pricing, sales count, and URLs.
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token", "")

    async with httpx.AsyncClient(
        base_url=GUMROAD_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as client:
        r = await client.get("products")
        r.raise_for_status()
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Gumroad API error: {data.get('message', 'Unknown error')}")

    products = data.get("products", [])
    log.info("gumroad.list_products", count=len(products))
    return {
        "products": products,
        "count": len(products),
        "success": True,
    }


@register_node("gumroad.list_sales")
async def gumroad_list_sales(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List sales for a Gumroad product or across all products.

    config:
      product_id  — filter by specific product permalink/ID (optional)
      after       — ISO date to list sales after (optional, e.g. '2024-01-01')
      before      — ISO date to list sales before (optional)
      email       — filter by buyer email (optional)
      page_key    — pagination cursor (optional)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token", "")

    params: dict = {}
    product_id = config.get("product_id") or input_data.get("product_id")
    after = config.get("after") or input_data.get("after")
    before = config.get("before") or input_data.get("before")
    email = config.get("email") or input_data.get("email")
    page_key = config.get("page_key") or input_data.get("page_key")

    if product_id:
        params["product_id"] = product_id
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    if email:
        params["email"] = email
    if page_key:
        params["page_key"] = page_key

    async with httpx.AsyncClient(
        base_url=GUMROAD_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as client:
        r = await client.get("sales", params=params)
        r.raise_for_status()
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Gumroad API error: {data.get('message', 'Unknown error')}")

    sales = data.get("sales", [])
    log.info("gumroad.list_sales", count=len(sales), product_id=product_id)
    return {
        "sales": sales,
        "count": len(sales),
        "next_page_key": data.get("next_page_key"),
        "success": True,
    }


@register_node("gumroad.get_sale")
async def gumroad_get_sale(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch details of a single Gumroad sale by ID.

    config/input_data:
      sale_id — Gumroad sale ID (required)
    """
    creds = await get_credential_data(credential_id, db)
    token = creds.get("access_token") or creds.get("token", "")

    sale_id = config.get("sale_id") or input_data.get("sale_id")
    if not sale_id:
        raise ValueError("sale_id is required for gumroad.get_sale")

    async with httpx.AsyncClient(
        base_url=GUMROAD_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as client:
        r = await client.get(f"sales/{sale_id}")
        r.raise_for_status()
        data = r.json()

    if not data.get("success"):
        raise RuntimeError(f"Gumroad API error: {data.get('message', 'Unknown error')}")

    sale = data.get("sale", {})
    log.info("gumroad.get_sale", sale_id=sale_id, email=sale.get("email"))
    return {
        "sale": sale,
        "sale_id": sale_id,
        "success": True,
    }


@register_node("gumroad.verify_license")
async def gumroad_verify_license(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Verify a Gumroad product license key.

    config/input_data:
      product_id    — product permalink (required)
      license_key   — license key to verify (required)
      increment_uses — bool, whether to increment use count (default False)

    Note: this endpoint does not require authentication.
    """
    product_id = config.get("product_id") or input_data.get("product_id")
    license_key = config.get("license_key") or input_data.get("license_key")
    increment_uses = bool(config.get("increment_uses") or input_data.get("increment_uses", False))

    if not product_id or not license_key:
        raise ValueError("product_id and license_key are required for gumroad.verify_license")

    payload = {
        "product_id": product_id,
        "license_key": license_key,
        "increment_uses_count": "true" if increment_uses else "false",
    }

    async with httpx.AsyncClient(base_url=GUMROAD_BASE, timeout=30) as client:
        r = await client.post("licenses/verify", data=payload)
        r.raise_for_status()
        data = r.json()

    success = data.get("success", False)
    purchase = data.get("purchase", {})
    log.info("gumroad.verify_license", product_id=product_id, valid=success)
    return {
        "valid": success,
        "purchase": purchase,
        "uses": purchase.get("uses", 0),
        "product_name": data.get("product", {}).get("name"),
        "message": data.get("message", ""),
        "success": success,
    }
