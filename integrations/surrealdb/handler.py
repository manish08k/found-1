"""SurrealDB integration — multi-model database."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base(config: dict) -> str:
    return config.get("url", "http://localhost:8000").rstrip("/")


def _headers(config: dict) -> dict:
    import base64
    creds = base64.b64encode(f"{config.get('username', 'root')}:{config.get('password', 'root')}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "NS": config.get("namespace", "test"),
        "DB": config.get("database", "test"),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@register_node("surrealdb.query")
async def surrealdb_query(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/sql", content=merged.get("query", "SELECT * FROM table;"), headers={"Content-Type": "text/plain"})
        r.raise_for_status()
    return {"result": r.json()}


@register_node("surrealdb.create_record")
async def surrealdb_create_record(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    table = merged.get("table", "")
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(f"{_base(merged)}/key/{table}", json=merged.get("data", {}))
        r.raise_for_status()
    return {"result": r.json()}
