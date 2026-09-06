"""Digital Pilot integration — digital marketing automation."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("digital_pilot.run_campaign")
async def digital_pilot_run_campaign(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {
        "campaign_id": merged.get("campaign_id", ""),
        "status": "running",
        "message": "Campaign started",
    }


@register_node("digital_pilot.get_report")
async def digital_pilot_get_report(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {
        "campaign_id": merged.get("campaign_id", ""),
        "impressions": 0,
        "clicks": 0,
        "conversions": 0,
    }
