"""Mixmax sales email integration — sequences and recipients."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

MIXMAX_BASE = "https://api.mixmax.com/v1"


@register_node("mixmax.list_sequences")
async def mixmax_list_sequences(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all Mixmax sequences.

    config/input_data:
      api_key — Mixmax API token (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""

    headers = {"X-API-Token": api_key}
    url = f"{MIXMAX_BASE}/sequences"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    sequences = data.get("results", data) if isinstance(data, dict) else data
    log.info("mixmax.list_sequences", count=len(sequences) if isinstance(sequences, list) else None)
    return {"sequences": sequences}


@register_node("mixmax.list_recipients")
async def mixmax_list_recipients(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List recipients of a Mixmax sequence.

    config/input_data:
      api_key     — Mixmax API token (required)
      sequence_id — sequence ID (required)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    sequence_id = merged.get("sequence_id") or ""

    if not sequence_id:
        raise ValueError("sequence_id is required for mixmax.list_recipients")

    headers = {"X-API-Token": api_key}
    url = f"{MIXMAX_BASE}/sequences/{sequence_id}/recipients"

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

    recipients = data.get("results", data) if isinstance(data, dict) else data
    log.info("mixmax.list_recipients", sequence_id=sequence_id, count=len(recipients) if isinstance(recipients, list) else None)
    return {"recipients": recipients, "sequence_id": sequence_id}


@register_node("mixmax.add_recipient")
async def mixmax_add_recipient(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Add a recipient to a Mixmax sequence.

    config/input_data:
      api_key     — Mixmax API token (required)
      sequence_id — sequence ID (required)
      email       — recipient email (required)
      variables   — dict of merge variables (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    sequence_id = merged.get("sequence_id") or ""
    email = merged.get("email") or ""
    variables = merged.get("variables") or {}

    if not sequence_id:
        raise ValueError("sequence_id is required for mixmax.add_recipient")
    if not email:
        raise ValueError("email is required for mixmax.add_recipient")

    headers = {"X-API-Token": api_key}
    url = f"{MIXMAX_BASE}/sequences/{sequence_id}/recipients"
    payload = {"email": email, "variables": variables}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    log.info("mixmax.add_recipient", sequence_id=sequence_id, email=email)
    return {"recipient": data, "sequence_id": sequence_id}
