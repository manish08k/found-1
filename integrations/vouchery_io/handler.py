"""Vouchery.io — promotions and voucher management integration."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

VOUCHERY_BASE = "https://app.vouchery.io/api/v2.0"


def _client(config: dict) -> httpx.AsyncClient:
    email = config.get("email", "")
    password = config.get("password", "")
    return httpx.AsyncClient(
        base_url=VOUCHERY_BASE,
        auth=(email, password),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30,
    )


@register_node("vouchery_io.list_campaigns")
async def vouchery_io_list_campaigns(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all campaigns from Vouchery.io.

    config:
      email    — Vouchery.io account email for HTTP Basic auth
      password — Vouchery.io account password for HTTP Basic auth
    """
    async with _client(config) as client:
        r = await client.get("/campaigns")
        r.raise_for_status()
        data = r.json()

    campaigns = data if isinstance(data, list) else data.get("campaigns", [])
    log.info("vouchery_io.list_campaigns", count=len(campaigns))
    return {"campaigns": campaigns, "count": len(campaigns)}


@register_node("vouchery_io.list_vouchers")
async def vouchery_io_list_vouchers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List vouchers for a specific campaign from Vouchery.io.

    config/input_data:
      email       — Vouchery.io account email
      password    — Vouchery.io account password
      campaign_id — campaign ID to list vouchers for (required)
      limit       — number of vouchers to return (default 25)
    """
    campaign_id = config.get("campaign_id") or input_data.get("campaign_id")
    limit = int(config.get("limit", 25))

    if not campaign_id:
        raise ValueError("campaign_id is required for vouchery_io.list_vouchers")

    async with _client(config) as client:
        r = await client.get(f"/campaigns/{campaign_id}/vouchers", params={"limit": limit})
        r.raise_for_status()
        data = r.json()

    vouchers = data if isinstance(data, list) else data.get("vouchers", [])
    log.info("vouchery_io.list_vouchers", campaign_id=campaign_id, count=len(vouchers))
    return {"vouchers": vouchers, "count": len(vouchers), "campaign_id": campaign_id}


@register_node("vouchery_io.redeem_voucher")
async def vouchery_io_redeem_voucher(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Redeem a voucher code via Vouchery.io.

    config/input_data:
      email          — Vouchery.io account email
      password       — Vouchery.io account password
      code           — voucher code to redeem (required)
      transaction_id — your transaction/order ID (required)
      amount         — total transaction cost for validation (required)
    """
    code = config.get("code") or input_data.get("code")
    transaction_id = config.get("transaction_id") or input_data.get("transaction_id")
    amount = config.get("amount") or input_data.get("amount")

    if not code:
        raise ValueError("code is required for vouchery_io.redeem_voucher")
    if not transaction_id:
        raise ValueError("transaction_id is required for vouchery_io.redeem_voucher")
    if amount is None:
        raise ValueError("amount is required for vouchery_io.redeem_voucher")

    payload = {
        "transaction_id": transaction_id,
        "total_transaction_cost": amount,
    }

    async with _client(config) as client:
        r = await client.patch(f"/redemptions/{code}", json=payload)
        r.raise_for_status()
        result = r.json()

    log.info("vouchery_io.redeem_voucher", code=code, transaction_id=transaction_id)
    return {"redemption": result, "code": code, "transaction_id": transaction_id}
