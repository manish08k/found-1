"""
MCP (Model Context Protocol) CLIENT — full surface: tools, resources,
and prompts, against any MCP-compliant server over Streamable HTTP
(JSON-RPC 2.0). Implemented directly with httpx rather than the official
`mcp` SDK — that SDK was tried and rejected for a concrete, verified
reason: installing it force-upgrades starlette/uvicorn/pydantic to
versions incompatible with this project's pinned FastAPI 0.115.0
(requires starlette<0.39.0), which would break the running app to gain
one integration. See integrations/mcp_/server.py for the SERVER side —
exposing AutoFlow's own workflows as MCP tools other clients can call.

Credential fields: {"server_url": "https://...", "auth_header": "Bearer ..."}
(auth_header optional).
"""
import itertools
import json

import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

MCP_PROTOCOL_VERSION = "2025-06-18"
_request_id_counter = itertools.count(1)


async def _rpc_call(client: httpx.AsyncClient, method: str, params: dict | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": next(_request_id_counter), "method": method}
    if params is not None:
        payload["params"] = params

    r = await client.post("/", json=payload, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })
    r.raise_for_status()

    content_type = r.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in r.text.splitlines():
            if line.startswith("data:"):
                body = json.loads(line[len("data:"):].strip())
                break
        else:
            raise ValueError("MCP server returned an SSE stream with no data event")
    else:
        body = r.json()

    if "error" in body:
        raise ValueError(f"MCP error {body['error'].get('code')}: {body['error'].get('message')}")
    return body.get("result", {})


def _build_client(creds: dict) -> httpx.AsyncClient:
    server_url = creds.get("server_url")
    if not server_url:
        raise ValueError("MCP credential is missing 'server_url'")
    headers = {}
    if creds.get("auth_header"):
        headers["Authorization"] = creds["auth_header"]
    return httpx.AsyncClient(base_url=server_url, headers=headers, timeout=30)


async def _initialize(client: httpx.AsyncClient) -> None:
    await _rpc_call(client, "initialize", {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "autoflow", "version": "1.0"},
    })


def _flatten_content(content_blocks: list) -> str:
    return "\n".join(b.get("text", "") for b in content_blocks if isinstance(b, dict) and b.get("type") == "text")


@register_node("mcp.list_tools")
async def mcp_list_tools(config: dict, input_data: dict, credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    async with _build_client(creds) as client:
        await _initialize(client)
        result = await _rpc_call(client, "tools/list")
    return {
        "tools": [
            {"name": t["name"], "description": t.get("description", ""), "input_schema": t.get("inputSchema", {})}
            for t in result.get("tools", [])
        ]
    }


@register_node("mcp.call_tool")
async def mcp_call_tool(config: dict, input_data: dict, credential_id: str, db) -> dict:
    tool_name = config.get("tool_name") or input_data.get("tool_name")
    arguments = config.get("arguments") or input_data.get("arguments") or {}
    if not tool_name:
        raise ValueError("mcp.call_tool requires 'tool_name'")
    if not isinstance(arguments, dict):
        raise ValueError("mcp.call_tool: 'arguments' must be a JSON object")

    creds = await get_credential_data(credential_id, db)
    async with _build_client(creds) as client:
        await _initialize(client)
        result = await _rpc_call(client, "tools/call", {"name": tool_name, "arguments": arguments})

    content_blocks = result.get("content", [])
    return {
        "text": _flatten_content(content_blocks),
        "content": content_blocks,
        "is_error": result.get("isError", False),
    }


@register_node("mcp.list_resources")
async def mcp_list_resources(config: dict, input_data: dict, credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    async with _build_client(creds) as client:
        await _initialize(client)
        result = await _rpc_call(client, "resources/list")
    return {
        "resources": [
            {"uri": r["uri"], "name": r.get("name", ""), "description": r.get("description", ""), "mime_type": r.get("mimeType")}
            for r in result.get("resources", [])
        ]
    }


@register_node("mcp.read_resource")
async def mcp_read_resource(config: dict, input_data: dict, credential_id: str, db) -> dict:
    uri = config.get("uri") or input_data.get("uri")
    if not uri:
        raise ValueError("mcp.read_resource requires 'uri'")

    creds = await get_credential_data(credential_id, db)
    async with _build_client(creds) as client:
        await _initialize(client)
        result = await _rpc_call(client, "resources/read", {"uri": uri})

    contents = result.get("contents", [])
    text_parts = [c.get("text", "") for c in contents if "text" in c]
    return {"uri": uri, "text": "\n".join(text_parts), "contents": contents}


@register_node("mcp.list_prompts")
async def mcp_list_prompts(config: dict, input_data: dict, credential_id: str, db) -> dict:
    creds = await get_credential_data(credential_id, db)
    async with _build_client(creds) as client:
        await _initialize(client)
        result = await _rpc_call(client, "prompts/list")
    return {
        "prompts": [
            {"name": p["name"], "description": p.get("description", ""), "arguments": p.get("arguments", [])}
            for p in result.get("prompts", [])
        ]
    }


@register_node("mcp.get_prompt")
async def mcp_get_prompt(config: dict, input_data: dict, credential_id: str, db) -> dict:
    name = config.get("prompt_name") or input_data.get("prompt_name")
    arguments = config.get("arguments") or input_data.get("arguments") or {}
    if not name:
        raise ValueError("mcp.get_prompt requires 'prompt_name'")

    creds = await get_credential_data(credential_id, db)
    async with _build_client(creds) as client:
        await _initialize(client)
        result = await _rpc_call(client, "prompts/get", {"name": name, "arguments": arguments})

    messages = result.get("messages", [])
    parts = []
    for m in messages:
        content = m.get("content")
        blocks = content if isinstance(content, list) else [content] if content else []
        parts.append(_flatten_content(blocks))
    return {"messages": messages, "text": "\n".join(parts)}


async def test_connection(creds: dict) -> None:
    async with _build_client(creds) as client:
        await _initialize(client)
