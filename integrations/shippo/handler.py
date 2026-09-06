"""Shippo integration — shipments, rates, labels, tracking, and address validation."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SHIPPO_BASE = "https://api.goshippo.com"


def _shippo_headers(api_key: str) -> dict:
    return {
        "Authorization": f"ShippoToken {api_key}",
        "Content-Type": "application/json",
    }


@register_node("shippo.list_shipments")
async def shippo_list_shipments(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List shipments in Shippo.

    config:
      api_key  — Shippo API key (required)
      page     — page number (optional, default 1)
      results  — results per page (optional, default 25)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for shippo.list_shipments")

    params = {"page": merged.get("page", 1), "results": merged.get("results", 25)}

    async with httpx.AsyncClient(base_url=SHIPPO_BASE, timeout=30) as client:
        r = await client.get("/shipments", headers=_shippo_headers(api_key), params=params)
        r.raise_for_status()
        data = r.json()

    shipments = data.get("results", [])
    log.info("shippo.list_shipments", count=len(shipments))
    return {"shipments": shipments, "count": data.get("count", len(shipments)), "next": data.get("next")}


@register_node("shippo.create_shipment")
async def shippo_create_shipment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new shipment in Shippo.

    config:
      api_key        — Shippo API key (required)
      address_from   — sender address dict (required)
      address_to     — recipient address dict (required)
      parcels        — list of parcel dicts with dimensions/weight (required)
      async_         — process asynchronously: true/false (optional, default false)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for shippo.create_shipment")

    payload: dict = {
        "address_from": merged.get("address_from", {}),
        "address_to": merged.get("address_to", {}),
        "parcels": merged.get("parcels", []),
        "async": merged.get("async_", False),
    }

    async with httpx.AsyncClient(base_url=SHIPPO_BASE, timeout=30) as client:
        r = await client.post("/shipments", headers=_shippo_headers(api_key), json=payload)
        r.raise_for_status()
        shipment = r.json()

    shipment_id = shipment.get("object_id")
    log.info("shippo.create_shipment", shipment_id=shipment_id, status=shipment.get("status"))
    return {"shipment": shipment, "shipment_id": shipment_id}


@register_node("shippo.get_rates")
async def shippo_get_rates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get shipping rates for a Shippo shipment.

    config:
      api_key     — Shippo API key (required)
      shipment_id — shipment object ID to get rates for (required)
      currency    — currency code e.g. USD (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    shipment_id = merged.get("shipment_id")
    if not api_key or not shipment_id:
        raise ValueError("api_key and shipment_id are required for shippo.get_rates")

    params: dict = {}
    if merged.get("currency"):
        params["currency"] = merged["currency"]

    async with httpx.AsyncClient(base_url=SHIPPO_BASE, timeout=30) as client:
        r = await client.get(
            f"/shipments/{shipment_id}/rates",
            headers=_shippo_headers(api_key),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    rates = data.get("results", [])
    log.info("shippo.get_rates", shipment_id=shipment_id, count=len(rates))
    return {"rates": rates, "count": len(rates), "shipment_id": shipment_id}


@register_node("shippo.create_label")
async def shippo_create_label(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a shipping label (transaction) for a Shippo rate.

    config:
      api_key     — Shippo API key (required)
      rate        — rate object ID to purchase (required)
      label_format — label format: PDF/PNG/ZPLII (optional, default PDF)
      async_      — process asynchronously (optional, default false)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    rate = merged.get("rate")
    if not api_key or not rate:
        raise ValueError("api_key and rate are required for shippo.create_label")

    payload: dict = {
        "rate": rate,
        "label_file_type": merged.get("label_format", "PDF"),
        "async": merged.get("async_", False),
    }

    async with httpx.AsyncClient(base_url=SHIPPO_BASE, timeout=60) as client:
        r = await client.post("/transactions", headers=_shippo_headers(api_key), json=payload)
        r.raise_for_status()
        transaction = r.json()

    transaction_id = transaction.get("object_id")
    label_url = transaction.get("label_url")
    log.info("shippo.create_label", transaction_id=transaction_id, status=transaction.get("status"))
    return {"transaction": transaction, "transaction_id": transaction_id, "label_url": label_url}


@register_node("shippo.track_package")
async def shippo_track_package(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track a package using Shippo.

    config:
      api_key        — Shippo API key (required)
      tracking_number — tracking number (required)
      carrier        — carrier slug e.g. "usps", "fedex", "ups" (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    tracking_number = merged.get("tracking_number")
    carrier = merged.get("carrier")
    if not api_key or not tracking_number or not carrier:
        raise ValueError("api_key, tracking_number, and carrier are required")

    async with httpx.AsyncClient(base_url=SHIPPO_BASE, timeout=30) as client:
        r = await client.get(
            f"/tracks/{carrier}/{tracking_number}",
            headers=_shippo_headers(api_key),
        )
        r.raise_for_status()
        tracking = r.json()

    status = tracking.get("tracking_status", {}).get("status")
    log.info("shippo.track_package", tracking_number=tracking_number, carrier=carrier, status=status)
    return {"tracking": tracking, "tracking_number": tracking_number, "carrier": carrier, "status": status}


@register_node("shippo.validate_address")
async def shippo_validate_address(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Validate a shipping address using Shippo.

    config:
      api_key   — Shippo API key (required)
      name      — recipient name (required)
      street1   — street address line 1 (required)
      city      — city (required)
      state     — state/province code (required)
      zip       — postal/zip code (required)
      country   — ISO country code e.g. "US" (required)
      street2   — street address line 2 (optional)
      phone     — phone number (optional)
      email     — email address (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required for shippo.validate_address")

    payload: dict = {
        "name": merged.get("name", ""),
        "street1": merged.get("street1", ""),
        "city": merged.get("city", ""),
        "state": merged.get("state", ""),
        "zip": merged.get("zip", ""),
        "country": merged.get("country", ""),
        "validate": True,
    }
    for field in ["street2", "phone", "email"]:
        if merged.get(field):
            payload[field] = merged[field]

    async with httpx.AsyncClient(base_url=SHIPPO_BASE, timeout=30) as client:
        r = await client.post("/addresses", headers=_shippo_headers(api_key), json=payload)
        r.raise_for_status()
        address = r.json()

    is_valid = address.get("validation_results", {}).get("is_valid", False)
    log.info("shippo.validate_address", is_valid=is_valid)
    return {"address": address, "is_valid": is_valid, "object_id": address.get("object_id")}
