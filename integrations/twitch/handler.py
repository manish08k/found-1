"""Twitch Helix API integration — users, streams, channels, search."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TWITCH_BASE = "https://api.twitch.tv/helix"


def _headers(access_token: str, client_id: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": client_id,
    }


@register_node("twitch.get_user")
async def twitch_get_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get Twitch user info by login name.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      client_id    — Twitch application client ID (required)
      username     — Twitch login name (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    client_id = config.get("client_id") or input_data.get("client_id")
    if not access_token or not client_id:
        raise ValueError("access_token and client_id are required for twitch.get_user")
    username = config.get("username") or input_data.get("username")
    if not username:
        raise ValueError("username is required for twitch.get_user")

    async with httpx.AsyncClient(base_url=TWITCH_BASE, timeout=30) as client:
        r = await client.get("/users", headers=_headers(access_token, client_id), params={"login": username})
        r.raise_for_status()
        data = r.json()

    users = data.get("data", [])
    user = users[0] if users else {}
    log.info("twitch.get_user", username=username, found=bool(user))
    return {"user": user, "username": username}


@register_node("twitch.get_stream")
async def twitch_get_stream(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get live stream info for a Twitch user.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      client_id    — Twitch application client ID (required)
      username     — Twitch login name (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    client_id = config.get("client_id") or input_data.get("client_id")
    if not access_token or not client_id:
        raise ValueError("access_token and client_id are required for twitch.get_stream")
    username = config.get("username") or input_data.get("username")
    if not username:
        raise ValueError("username is required for twitch.get_stream")

    async with httpx.AsyncClient(base_url=TWITCH_BASE, timeout=30) as client:
        r = await client.get(
            "/streams", headers=_headers(access_token, client_id), params={"user_login": username}
        )
        r.raise_for_status()
        data = r.json()

    streams = data.get("data", [])
    stream = streams[0] if streams else {}
    live = bool(stream)
    log.info("twitch.get_stream", username=username, live=live)
    return {"stream": stream, "username": username, "live": live}


@register_node("twitch.get_channel")
async def twitch_get_channel(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get Twitch channel information by broadcaster ID.

    config/input_data:
      access_token    — OAuth2 Bearer token (required)
      client_id       — Twitch application client ID (required)
      broadcaster_id  — Twitch broadcaster/user ID (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    client_id = config.get("client_id") or input_data.get("client_id")
    if not access_token or not client_id:
        raise ValueError("access_token and client_id are required for twitch.get_channel")
    broadcaster_id = config.get("broadcaster_id") or input_data.get("broadcaster_id")
    if not broadcaster_id:
        raise ValueError("broadcaster_id is required for twitch.get_channel")

    async with httpx.AsyncClient(base_url=TWITCH_BASE, timeout=30) as client:
        r = await client.get(
            "/channels",
            headers=_headers(access_token, client_id),
            params={"broadcaster_id": broadcaster_id},
        )
        r.raise_for_status()
        data = r.json()

    channels = data.get("data", [])
    channel = channels[0] if channels else {}
    log.info("twitch.get_channel", broadcaster_id=broadcaster_id, found=bool(channel))
    return {"channel": channel, "broadcaster_id": broadcaster_id}


@register_node("twitch.search_channels")
async def twitch_search_channels(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search Twitch channels by query string.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      client_id    — Twitch application client ID (required)
      query        — search query (required)
      first        — number of results to return (default 10)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    client_id = config.get("client_id") or input_data.get("client_id")
    if not access_token or not client_id:
        raise ValueError("access_token and client_id are required for twitch.search_channels")
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("query is required for twitch.search_channels")
    first = int(config.get("first", 10))

    async with httpx.AsyncClient(base_url=TWITCH_BASE, timeout=30) as client:
        r = await client.get(
            "/search/channels",
            headers=_headers(access_token, client_id),
            params={"query": query, "first": first},
        )
        r.raise_for_status()
        data = r.json()

    channels = data.get("data", [])
    log.info("twitch.search_channels", query=query, count=len(channels))
    return {
        "channels": channels,
        "count": len(channels),
        "query": query,
        "pagination": data.get("pagination", {}),
    }
