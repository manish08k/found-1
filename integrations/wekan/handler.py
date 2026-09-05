"""WeKan kanban board integration — boards, lists, and cards management."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


async def _wekan_login(client: httpx.AsyncClient, config: dict) -> str:
    """Authenticate with WeKan and return a bearer token."""
    username = config.get("username", "")
    password = config.get("password", "")
    if not username or not password:
        raise ValueError("username and password are required for WeKan authentication")

    r = await client.post("/users/login", json={"username": username, "password": password})
    r.raise_for_status()
    data = r.json()
    token = data.get("token") or data.get("authToken")
    if not token:
        raise ValueError("WeKan login did not return a token")
    return token


def _wekan_client(config: dict) -> httpx.AsyncClient:
    host = config.get("host", "").rstrip("/")
    if not host:
        raise ValueError("host is required for WeKan integration")
    base_url = f"{host}/api"
    return httpx.AsyncClient(base_url=base_url, timeout=30)


@register_node("wekan.list_boards")
async def wekan_list_boards(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all boards accessible to the authenticated user.

    config/input_data:
      host     — WeKan instance URL (e.g. https://wekan.example.com)
      username — WeKan username
      password — WeKan password
      user_id  — WeKan user ID to list boards for
    """
    merged = {**config, **input_data}
    user_id = merged.get("user_id")
    if not user_id:
        raise ValueError("user_id is required for wekan.list_boards")

    async with _wekan_client(merged) as client:
        token = await _wekan_login(client, merged)
        r = await client.get(
            "/boards",
            params={"userId": user_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        boards = r.json()

    log.info("wekan.list_boards", count=len(boards) if isinstance(boards, list) else "unknown")
    return {"boards": boards}


@register_node("wekan.get_board")
async def wekan_get_board(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific WeKan board.

    config/input_data:
      host     — WeKan instance URL
      username — WeKan username
      password — WeKan password
      board_id — board identifier
    """
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    if not board_id:
        raise ValueError("board_id is required for wekan.get_board")

    async with _wekan_client(merged) as client:
        token = await _wekan_login(client, merged)
        r = await client.get(
            f"/boards/{board_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        board = r.json()

    log.info("wekan.get_board", board_id=board_id)
    return board


@register_node("wekan.list_lists")
async def wekan_list_lists(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all lists in a WeKan board.

    config/input_data:
      host     — WeKan instance URL
      username — WeKan username
      password — WeKan password
      board_id — board identifier
    """
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    if not board_id:
        raise ValueError("board_id is required for wekan.list_lists")

    async with _wekan_client(merged) as client:
        token = await _wekan_login(client, merged)
        r = await client.get(
            f"/boards/{board_id}/lists",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        lists = r.json()

    log.info("wekan.list_lists", board_id=board_id, count=len(lists) if isinstance(lists, list) else "unknown")
    return {"lists": lists}


@register_node("wekan.create_card")
async def wekan_create_card(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new card in a WeKan board list.

    config/input_data:
      host        — WeKan instance URL
      username    — WeKan username
      password    — WeKan password
      board_id    — board identifier
      list_id     — list identifier
      title       — card title
      description — card description (optional)
      authorId    — author user ID
    """
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    list_id = merged.get("list_id")
    title = merged.get("title")
    author_id = merged.get("authorId")

    if not board_id:
        raise ValueError("board_id is required for wekan.create_card")
    if not list_id:
        raise ValueError("list_id is required for wekan.create_card")
    if not title:
        raise ValueError("title is required for wekan.create_card")
    if not author_id:
        raise ValueError("authorId is required for wekan.create_card")

    payload = {
        "title": title,
        "authorId": author_id,
    }
    if merged.get("description"):
        payload["description"] = merged["description"]

    async with _wekan_client(merged) as client:
        token = await _wekan_login(client, merged)
        r = await client.post(
            f"/boards/{board_id}/lists/{list_id}/cards",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        result = r.json()

    log.info("wekan.create_card", board_id=board_id, list_id=list_id, title=title)
    return result


@register_node("wekan.get_card")
async def wekan_get_card(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get details of a specific WeKan card.

    config/input_data:
      host     — WeKan instance URL
      username — WeKan username
      password — WeKan password
      board_id — board identifier
      list_id  — list identifier
      card_id  — card identifier
    """
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    list_id = merged.get("list_id")
    card_id = merged.get("card_id")

    if not board_id:
        raise ValueError("board_id is required for wekan.get_card")
    if not list_id:
        raise ValueError("list_id is required for wekan.get_card")
    if not card_id:
        raise ValueError("card_id is required for wekan.get_card")

    async with _wekan_client(merged) as client:
        token = await _wekan_login(client, merged)
        r = await client.get(
            f"/boards/{board_id}/lists/{list_id}/cards/{card_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
        card = r.json()

    log.info("wekan.get_card", board_id=board_id, list_id=list_id, card_id=card_id)
    return card


@register_node("wekan.update_card")
async def wekan_update_card(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update a WeKan card's fields.

    config/input_data:
      host        — WeKan instance URL
      username    — WeKan username
      password    — WeKan password
      board_id    — board identifier
      list_id     — list identifier
      card_id     — card identifier
      title       — new card title (optional)
      description — new description (optional)
      listId      — new list ID to move card (optional)
      (any other fields will be passed through to the API)
    """
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    list_id = merged.get("list_id")
    card_id = merged.get("card_id")

    if not board_id:
        raise ValueError("board_id is required for wekan.update_card")
    if not list_id:
        raise ValueError("list_id is required for wekan.update_card")
    if not card_id:
        raise ValueError("card_id is required for wekan.update_card")

    # Build update payload from any card fields provided (excluding connection params)
    excluded = {"host", "username", "password", "board_id", "list_id", "card_id"}
    payload = {k: v for k, v in merged.items() if k not in excluded and v is not None}

    async with _wekan_client(merged) as client:
        token = await _wekan_login(client, merged)
        r = await client.put(
            f"/boards/{board_id}/lists/{list_id}/cards/{card_id}",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        result = r.json() if r.content else {"updated": True}

    log.info("wekan.update_card", board_id=board_id, list_id=list_id, card_id=card_id)
    return result
