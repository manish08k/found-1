"""Fragment integration — accounting and treasury for crypto."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)
BASE = "https://api.fragment.dev/graphql"


def _headers(config: dict) -> dict:
    return {"Authorization": f"Bearer {config.get('api_key', '')}", "Content-Type": "application/json"}


@register_node("fragment.get_ledger")
async def fragment_get_ledger(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    ledger_id = merged.get("ledger_id", "")
    query = f"""query {{ ledger(ik: "{ledger_id}") {{ id name balance {{ amount currency }} }} }}"""
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(BASE, json={"query": query})
        r.raise_for_status()
    return r.json()


@register_node("fragment.post_transaction")
async def fragment_post_transaction(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    async with httpx.AsyncClient(headers=_headers(merged), timeout=30) as client:
        r = await client.post(BASE, json={
            "query": """mutation PostTransaction($post: PostLedgerEntriesInput!) { postLedgerEntries(post: $post) { id } }""",
            "variables": {"post": merged.get("post", {})},
        })
        r.raise_for_status()
    return r.json()
