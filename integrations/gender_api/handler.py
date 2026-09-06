"""Gender API integration — gender determination from first names."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

GENDER_API_BASE = "https://api.gender-api.com"


@register_node("gender_api.determine_gender")
async def gender_api_determine_gender(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Determine the gender of a person based on their first name.

    config:
      api_key  — Gender API key (required)
      name     — first name to determine gender for (required)
      country  — ISO 3166-1 alpha-2 country code to improve accuracy (optional)
      language — ISO 639-1 language code (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    name = merged.get("name")
    if not name:
        raise ValueError("name is required for gender_api.determine_gender")

    params = {"name": name, "key": api_key}
    if merged.get("country"):
        params["country"] = merged["country"]
    if merged.get("language"):
        params["language"] = merged["language"]

    async with httpx.AsyncClient(base_url=GENDER_API_BASE, timeout=30) as client:
        r = await client.get("/get", params=params)
        r.raise_for_status()
        data = r.json()

    log.info("gender_api.determine_gender", name=name, gender=data.get("gender"), accuracy=data.get("accuracy"))
    return {
        "name": data.get("name"),
        "gender": data.get("gender"),
        "accuracy": data.get("accuracy"),
        "samples": data.get("samples"),
        "country": data.get("country"),
        "raw": data,
    }


@register_node("gender_api.batch_determine")
async def gender_api_batch_determine(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Determine genders for a batch of first names.

    config:
      api_key  — Gender API key (required)
      names    — list of first names to process (required)
      country  — ISO 3166-1 alpha-2 country code (optional)
      language — ISO 639-1 language code (optional)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    names = merged.get("names")
    if not names:
        raise ValueError("names is required for gender_api.batch_determine")
    if isinstance(names, str):
        names = [n.strip() for n in names.split(",") if n.strip()]

    params = {"key": api_key}
    if merged.get("country"):
        params["country"] = merged["country"]
    if merged.get("language"):
        params["language"] = merged["language"]

    results = []
    async with httpx.AsyncClient(base_url=GENDER_API_BASE, timeout=60) as client:
        for name in names:
            r = await client.get("/get", params={**params, "name": name})
            r.raise_for_status()
            results.append(r.json())

    log.info("gender_api.batch_determine", total=len(names), processed=len(results))
    return {"results": results, "count": len(results)}
