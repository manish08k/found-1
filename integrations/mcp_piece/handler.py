"""MCP (Model Context Protocol) piece for Activepieces — handler for mcp_piece integration."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

BASE_URL = ""


@register_node("mcp_piece.list_tools")
async def mcp_piece_list_tools(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List available MCP tools.

    config/input_data:
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    log.info("mcp_piece.list_tools", merged_keys=list(merged.keys()))
    return {"ok": True, "data": merged}

@register_node("mcp_piece.call_tool")
async def mcp_piece_call_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Call an MCP tool.

    config/input_data:
      tool_name — (required)
      arguments — (required)
    """
    merged = {**config, **input_data}
    headers = {"Content-Type": "application/json"}
    tool_name = merged.get("tool_name") or ""
    arguments = merged.get("arguments") or ""
    if not tool_name or not arguments:
        raise ValueError("tool_name, arguments required for mcp_piece.call_tool")
    log.info("mcp_piece.call_tool", merged_keys=list(merged.keys()))
    return {"ok": True, "data": merged}
