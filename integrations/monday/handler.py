"""
Monday.com integration — boards, items, columns, updates.
Nodes: monday.get_boards, monday.get_items, monday.create_item,
       monday.update_item, monday.create_update, monday.move_item
"""
import httpx
import structlog
from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

MONDAY_API = "https://api.monday.com/v2"


def _headers(config):
    api_key = config.get("api_key") or getattr(settings, "MONDAY_API_KEY", "")
    if not api_key:
        raise ValueError("monday nodes require MONDAY_API_KEY or 'api_key'")
    return {"Authorization": api_key, "Content-Type": "application/json", "API-Version": "2024-01"}


async def _query(gql: str, variables: dict, config: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            MONDAY_API,
            json={"query": gql, "variables": variables},
            headers=_headers(config),
        )
        r.raise_for_status()
        return r.json()


@register_node("monday.get_boards")
async def monday_get_boards(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    limit = min(int(merged.get("limit", 10)), 50)
    data = await _query(
        "query($limit: Int) { boards(limit: $limit) { id name description state } }",
        {"limit": limit},
        merged,
    )
    boards = data["data"]["boards"]
    return {"boards": boards, "count": len(boards)}


@register_node("monday.get_items")
async def monday_get_items(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    if not board_id:
        raise ValueError("monday.get_items requires 'board_id'")

    limit = min(int(merged.get("limit", 25)), 100)
    data = await _query(
        """
        query($board_id: ID!, $limit: Int) {
          boards(ids: [$board_id]) {
            items_page(limit: $limit) {
              items {
                id name state
                column_values { id text value }
              }
            }
          }
        }
        """,
        {"board_id": board_id, "limit": limit},
        merged,
    )
    items = data["data"]["boards"][0]["items_page"]["items"]
    return {"items": items, "count": len(items)}


@register_node("monday.create_item")
async def monday_create_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    item_name = merged.get("name") or merged.get("item_name", "New Item")
    column_values = merged.get("column_values")

    if not board_id:
        raise ValueError("monday.create_item requires 'board_id'")

    import json as json_mod
    col_vals_str = json_mod.dumps(column_values) if column_values else "{}"

    data = await _query(
        """
        mutation($board_id: ID!, $name: String!, $col_vals: JSON) {
          create_item(board_id: $board_id, item_name: $name, column_values: $col_vals) {
            id name
          }
        }
        """,
        {"board_id": board_id, "name": item_name, "col_vals": col_vals_str},
        merged,
    )
    item = data["data"]["create_item"]
    return {"item": item, "ok": True}


@register_node("monday.update_item")
async def monday_update_item(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    board_id = merged.get("board_id")
    item_id = merged.get("item_id")
    column_id = merged.get("column_id")
    value = merged.get("value", "")

    if not all([board_id, item_id, column_id]):
        raise ValueError("monday.update_item requires 'board_id', 'item_id', 'column_id'")

    import json as json_mod
    val_str = json_mod.dumps(value) if not isinstance(value, str) else json_mod.dumps({"text": value})

    data = await _query(
        """
        mutation($board_id: ID!, $item_id: ID!, $col_id: String!, $value: JSON!) {
          change_simple_column_value(board_id: $board_id, item_id: $item_id, column_id: $col_id, value: $value) {
            id
          }
        }
        """,
        {"board_id": board_id, "item_id": item_id, "col_id": column_id, "value": val_str},
        merged,
    )
    return {"ok": True, "item_id": item_id}


@register_node("monday.create_update")
async def monday_create_update(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    item_id = merged.get("item_id")
    body = merged.get("body") or merged.get("text", "")

    if not item_id:
        raise ValueError("monday.create_update requires 'item_id'")

    data = await _query(
        """
        mutation($item_id: ID!, $body: String!) {
          create_update(item_id: $item_id, body: $body) { id body }
        }
        """,
        {"item_id": item_id, "body": body},
        merged,
    )
    return {"update": data["data"]["create_update"], "ok": True}
