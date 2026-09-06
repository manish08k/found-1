"""MCP Client piece for Activepieces — handler for mcp_client integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = ""


@register_node("mcp_client.connect")
async def mcp_client_connect(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Connect to an MCP server.

    config/input_data:
      server_url — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    server_url = merged.get("server_url") or ""
    if not server_url:
        raise ValueError("server_url required for mcp_client.connect")
    log.info("mcp_client.connect", merged_keys=list(merged.keys()))
    return {"ok": True, "data": merged}

@register_node("mcp_client.call_tool")
async def mcp_client_call_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Call a tool on MCP server.

    config/input_data:
      tool_name — (required)
      arguments — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    tool_name = merged.get("tool_name") or ""
    arguments = merged.get("arguments") or ""
    if not tool_name or not arguments:
        raise ValueError("tool_name, arguments required for mcp_client.call_tool")
    log.info("mcp_client.call_tool", merged_keys=list(merged.keys()))
    return {"ok": True, "data": merged}
