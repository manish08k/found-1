"""Chess.com integration — player stats, games, puzzles."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.chess.com/pub"


@register_node("chess_com.get_player")
async def chess_com_get_player(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    username = merged.get("username", "")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE}/player/{username}")
        r.raise_for_status()
    return r.json()


@register_node("chess_com.get_player_stats")
async def chess_com_get_player_stats(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    username = merged.get("username", "")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE}/player/{username}/stats")
        r.raise_for_status()
    return r.json()


@register_node("chess_com.get_daily_puzzle")
async def chess_com_get_daily_puzzle(config: dict, input_data: dict, credential_id: str, db) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE}/puzzle")
        r.raise_for_status()
    return r.json()
