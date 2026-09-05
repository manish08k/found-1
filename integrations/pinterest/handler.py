"""Pinterest API v5 integration — boards, pins, user account."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

PINTEREST_BASE = "https://api.pinterest.com/v5"


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


@register_node("pinterest.list_boards")
async def pinterest_list_boards(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List the authenticated user's Pinterest boards.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      page_size    — number of boards per page (default 25)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for pinterest.list_boards")
    page_size = int(config.get("page_size", 25))

    async with httpx.AsyncClient(base_url=PINTEREST_BASE, timeout=30) as client:
        r = await client.get("/boards", headers=_headers(access_token), params={"page_size": page_size})
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    log.info("pinterest.list_boards", count=len(items))
    return {
        "boards": items,
        "count": len(items),
        "bookmark": data.get("bookmark"),
    }


@register_node("pinterest.list_pins")
async def pinterest_list_pins(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List pins on a Pinterest board.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      board_id     — Pinterest board ID (required)
      page_size    — number of pins per page (default 25)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for pinterest.list_pins")
    board_id = config.get("board_id") or input_data.get("board_id")
    if not board_id:
        raise ValueError("board_id is required for pinterest.list_pins")
    page_size = int(config.get("page_size", 25))

    async with httpx.AsyncClient(base_url=PINTEREST_BASE, timeout=30) as client:
        r = await client.get(
            f"/boards/{board_id}/pins",
            headers=_headers(access_token),
            params={"page_size": page_size},
        )
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    log.info("pinterest.list_pins", board_id=board_id, count=len(items))
    return {
        "pins": items,
        "count": len(items),
        "board_id": board_id,
        "bookmark": data.get("bookmark"),
    }


@register_node("pinterest.create_pin")
async def pinterest_create_pin(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new Pinterest pin.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
      board_id     — Pinterest board ID (required)
      image_url    — public URL of the image (required)
      title        — pin title (optional)
      description  — pin description (optional)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for pinterest.create_pin")
    board_id = config.get("board_id") or input_data.get("board_id")
    if not board_id:
        raise ValueError("board_id is required for pinterest.create_pin")
    image_url = config.get("image_url") or input_data.get("image_url")
    if not image_url:
        raise ValueError("image_url is required for pinterest.create_pin")

    payload = {
        "board_id": board_id,
        "media_source": {"source_type": "image_url", "url": image_url},
        "title": config.get("title") or input_data.get("title", ""),
        "description": config.get("description") or input_data.get("description", ""),
    }

    async with httpx.AsyncClient(base_url=PINTEREST_BASE, timeout=30) as client:
        r = await client.post("/pins", headers=_headers(access_token), json=payload)
        r.raise_for_status()
        pin = r.json()

    log.info("pinterest.create_pin", board_id=board_id, pin_id=pin.get("id"))
    return {"pin": pin, "pin_id": pin.get("id"), "board_id": board_id}


@register_node("pinterest.get_user_account")
async def pinterest_get_user_account(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the authenticated Pinterest user account details.

    config/input_data:
      access_token — OAuth2 Bearer token (required)
    """
    access_token = config.get("access_token") or input_data.get("access_token")
    if not access_token:
        raise ValueError("access_token is required for pinterest.get_user_account")

    async with httpx.AsyncClient(base_url=PINTEREST_BASE, timeout=30) as client:
        r = await client.get("/user_account", headers=_headers(access_token))
        r.raise_for_status()
        user = r.json()

    log.info("pinterest.get_user_account", username=user.get("username"))
    return {"user": user, "username": user.get("username")}
