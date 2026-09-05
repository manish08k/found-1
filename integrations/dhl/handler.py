"""DHL integration — shipment tracking and creation via the DHL API."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DHL_TRACK_BASE = "https://api-eu.dhl.com/track"
DHL_SHIP_BASE = "https://api-eu.dhl.com/ship/v1"


def _api_key(config: dict) -> str:
    key = config.get("api_key") or ""
    if not key:
        raise ValueError("dhl nodes require 'api_key' in config")
    return key


def _tracking_headers(config: dict) -> dict:
    return {
        "DHL-API-Key": _api_key(config),
        "Accept": "application/json",
    }


def _shipping_headers(config: dict) -> dict:
    return {
        "DHL-API-Key": _api_key(config),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


@register_node("dhl.track_shipment")
async def dhl_track_shipment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Track a DHL shipment by tracking number.

    config:
      api_key         — DHL API key
      tracking_number — the shipment tracking number
    """
    merged = {**config, **input_data}
    tracking_number = merged.get("tracking_number")
    if not tracking_number:
        raise ValueError("dhl.track_shipment requires 'tracking_number'")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{DHL_TRACK_BASE}/shipments",
            params={"trackingNumber": tracking_number},
            headers=_tracking_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    shipments = data.get("shipments", [])
    log.info("dhl.track_shipment", tracking_number=tracking_number, shipments_found=len(shipments))
    return {"shipments": shipments, "tracking_number": tracking_number, "count": len(shipments)}


@register_node("dhl.get_shipment_events")
async def dhl_get_shipment_events(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve only the events array from a tracked DHL shipment.

    config:
      api_key         — DHL API key
      tracking_number — the shipment tracking number
    """
    merged = {**config, **input_data}
    tracking_number = merged.get("tracking_number")
    if not tracking_number:
        raise ValueError("dhl.get_shipment_events requires 'tracking_number'")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{DHL_TRACK_BASE}/shipments",
            params={"trackingNumber": tracking_number},
            headers=_tracking_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    shipments = data.get("shipments", [])
    events: list = []
    for shipment in shipments:
        events.extend(shipment.get("events", []))
    log.info("dhl.get_shipment_events", tracking_number=tracking_number, events_found=len(events))
    return {"events": events, "tracking_number": tracking_number, "count": len(events)}


@register_node("dhl.create_shipment")
async def dhl_create_shipment(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new DHL shipment and obtain a shipping label.

    config:
      api_key    — DHL API key
      shipper    — dict with shipper address/contact details
      recipient  — dict with recipient address/contact details
      packages   — list of package dicts (weight, dimensions, etc.)
    """
    merged = {**config, **input_data}
    shipper = merged.get("shipper")
    recipient = merged.get("recipient")
    packages = merged.get("packages")
    if not shipper:
        raise ValueError("dhl.create_shipment requires 'shipper' dict")
    if not recipient:
        raise ValueError("dhl.create_shipment requires 'recipient' dict")
    if not packages:
        raise ValueError("dhl.create_shipment requires 'packages' list")
    payload = {
        "shipper": shipper,
        "recipient": recipient,
        "packages": packages if isinstance(packages, list) else [packages],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{DHL_SHIP_BASE}/shipments",
            json=payload,
            headers=_shipping_headers(merged),
        )
        r.raise_for_status()
        data = r.json()
    log.info("dhl.create_shipment", shipment_id=data.get("shipmentTrackingNumber"))
    return {"shipment": data, "ok": True}
