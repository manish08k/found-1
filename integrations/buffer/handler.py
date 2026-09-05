"""Buffer social media scheduling integration — user, profiles, posts."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BUFFER_BASE = "https://api.bufferapp.com/1"


@register_node("buffer.get_user")
async def buffer_get_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the authenticated Buffer user profile.

    config/input_data:
      access_token — Buffer OAuth access token (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for buffer.get_user")

    async with httpx.AsyncClient(base_url=BUFFER_BASE, timeout=30) as client:
        r = await client.get("/user.json", params={"access_token": access_token})
        r.raise_for_status()
        user = r.json()

    log.info("buffer.get_user", user_id=user.get("id"))
    return {"user": user, "user_id": user.get("id")}


@register_node("buffer.list_profiles")
async def buffer_list_profiles(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List Buffer social media profiles for the authenticated user.

    config/input_data:
      access_token — Buffer OAuth access token (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for buffer.list_profiles")

    async with httpx.AsyncClient(base_url=BUFFER_BASE, timeout=30) as client:
        r = await client.get("/profiles.json", params={"access_token": access_token})
        r.raise_for_status()
        profiles = r.json()

    profiles = profiles if isinstance(profiles, list) else []
    log.info("buffer.list_profiles", count=len(profiles))
    return {"profiles": profiles, "count": len(profiles)}


@register_node("buffer.create_post")
async def buffer_create_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create and schedule a Buffer post to a social profile.

    config/input_data:
      access_token — Buffer OAuth access token (required)
      profile_id   — Buffer profile ID to post to (required)
      text         — post text content (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for buffer.create_post")
    profile_id = config.get("profile_id") or input_data.get("profile_id")
    if not profile_id:
        raise ValueError("profile_id is required for buffer.create_post")
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("text is required for buffer.create_post")

    payload = {
        "profile_ids[]": [profile_id],
        "text": text,
        "access_token": access_token,
    }

    async with httpx.AsyncClient(base_url=BUFFER_BASE, timeout=30) as client:
        r = await client.post("/updates/create.json", data=payload)
        r.raise_for_status()
        result = r.json()

    log.info("buffer.create_post", profile_id=profile_id, success=result.get("success"))
    return {"result": result, "success": result.get("success"), "profile_id": profile_id}


@register_node("buffer.list_updates")
async def buffer_list_updates(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List pending Buffer updates for a social profile.

    config/input_data:
      access_token — Buffer OAuth access token (required)
      profile_id   — Buffer profile ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for buffer.list_updates")
    profile_id = config.get("profile_id") or input_data.get("profile_id")
    if not profile_id:
        raise ValueError("profile_id is required for buffer.list_updates")

    async with httpx.AsyncClient(base_url=BUFFER_BASE, timeout=30) as client:
        r = await client.get(
            f"/profiles/{profile_id}/updates/pending.json",
            params={"access_token": access_token},
        )
        r.raise_for_status()
        data = r.json()

    updates = data.get("updates", [])
    log.info("buffer.list_updates", profile_id=profile_id, count=len(updates))
    return {
        "updates": updates,
        "count": len(updates),
        "profile_id": profile_id,
        "total": data.get("total"),
    }
