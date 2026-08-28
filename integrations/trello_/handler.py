"""
Trello integration. Credential fields: {"api_key": "...", "token": "..."}
— Trello's REST API authenticates via query-string `key`/`token` params
rather than a header, which is unusual but simple; both come from
https://trello.com/power-ups/admin (API key) and the token authorize flow
linked from that page.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

TRELLO_BASE = "https://api.trello.com/1"


async def _auth_params(credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    token = creds.get("token")
    if not api_key or not token:
        raise ValueError("Trello credential is missing 'api_key' or 'token'")
    return {"key": api_key, "token": token}


@register_node("trello.create_card")
async def trello_create_card(config: dict, input_data: dict, credential_id: str, db) -> dict:
    list_id = config.get("list_id") or input_data.get("list_id")
    name = config.get("name") or input_data.get("name")
    description = config.get("description") or input_data.get("description", "")
    if not list_id or not name:
        raise ValueError("trello.create_card requires 'list_id' and 'name'")

    auth = await _auth_params(credential_id, db)
    async with httpx.AsyncClient(base_url=TRELLO_BASE, timeout=30) as client:
        r = await client.post("/cards", params={**auth, "idList": list_id, "name": name, "desc": description})
        r.raise_for_status()
        data = r.json()

    return {"id": data["id"], "url": data["shortUrl"]}


@register_node("trello.move_card")
async def trello_move_card(config: dict, input_data: dict, credential_id: str, db) -> dict:
    card_id = config.get("card_id") or input_data.get("card_id")
    list_id = config.get("list_id") or input_data.get("list_id")
    if not card_id or not list_id:
        raise ValueError("trello.move_card requires 'card_id' and 'list_id'")

    auth = await _auth_params(credential_id, db)
    async with httpx.AsyncClient(base_url=TRELLO_BASE, timeout=30) as client:
        r = await client.put(f"/cards/{card_id}", params={**auth, "idList": list_id})
        r.raise_for_status()
        data = r.json()

    return {"id": data["id"], "idList": data["idList"]}


@register_node("trello.list_cards")
async def trello_list_cards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    list_id = config.get("list_id") or input_data.get("list_id")
    if not list_id:
        raise ValueError("trello.list_cards requires 'list_id'")

    auth = await _auth_params(credential_id, db)
    async with httpx.AsyncClient(base_url=TRELLO_BASE, timeout=30) as client:
        r = await client.get(f"/lists/{list_id}/cards", params=auth)
        r.raise_for_status()
        data = r.json()

    return {"cards": [{"id": c["id"], "name": c["name"], "url": c["shortUrl"]} for c in data]}


async def test_connection(creds: dict) -> None:
    api_key = creds.get("api_key")
    token = creds.get("token")
    if not api_key or not token:
        raise ValueError("Missing api_key or token")
    async with httpx.AsyncClient(base_url=TRELLO_BASE, timeout=10) as client:
        r = await client.get("/members/me", params={"key": api_key, "token": token})
        r.raise_for_status()
