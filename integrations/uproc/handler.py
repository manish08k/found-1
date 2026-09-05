"""UProc data enrichment integration — run tools, check balance, list tools."""
import base64
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

UPROC_BASE = "https://api.uproc.io/api/v2"


def _auth_headers(config: dict) -> dict:
    email = config.get("email", "")
    api_key = config.get("api_key", "")
    credentials = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


@register_node("uproc.run_tool")
async def uproc_run_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Run a UProc enrichment tool.

    config/input_data:
      email   — UProc account email
      api_key — UProc API key
      tool    — tool name (e.g. "getEmailFromLinkedinProfile")
      data    — dict of input parameters for the tool
    """
    merged = {**config, **input_data}
    tool_name = merged.get("tool")
    if not tool_name:
        raise ValueError("tool is required for uproc.run_tool")

    data = merged.get("data", {})
    headers = _auth_headers(merged)

    async with httpx.AsyncClient(base_url=UPROC_BASE, timeout=60) as client:
        r = await client.post(
            "/process",
            json={"tool": tool_name, "data": data},
            headers=headers,
        )
        r.raise_for_status()
        result = r.json()

    log.info("uproc.run_tool", tool=tool_name)
    return result


@register_node("uproc.get_balance")
async def uproc_get_balance(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get remaining UProc API credits.

    config/input_data:
      email   — UProc account email
      api_key — UProc API key
    """
    merged = {**config, **input_data}
    headers = _auth_headers(merged)

    async with httpx.AsyncClient(base_url=UPROC_BASE, timeout=30) as client:
        r = await client.get("/balance", headers=headers)
        r.raise_for_status()
        result = r.json()

    log.info("uproc.get_balance")
    return result


@register_node("uproc.list_tools")
async def uproc_list_tools(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available UProc tools.

    config/input_data:
      email   — UProc account email
      api_key — UProc API key
    """
    merged = {**config, **input_data}
    headers = _auth_headers(merged)

    async with httpx.AsyncClient(base_url=UPROC_BASE, timeout=30) as client:
        r = await client.get("/tools", headers=headers)
        r.raise_for_status()
        result = r.json()

    tools = result if isinstance(result, list) else result.get("tools", result)
    log.info("uproc.list_tools", count=len(tools) if isinstance(tools, list) else "unknown")
    return {"tools": tools}
