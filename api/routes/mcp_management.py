"""
MCP Server Management — register, discover, and manage external MCP servers.
"""
import json
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import MCPServer, User

log = structlog.get_logger(__name__)

router = APIRouter()


class MCPServerCreate(BaseModel):
    name: str
    url: str
    auth_type: str = "none"  # none, api_key, oauth
    api_key: Optional[str] = None


class MCPServerPermissions(BaseModel):
    allowed_tools: list[str] = []  # empty = all tools allowed


def _serialize(s: MCPServer) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "url": s.url,
        "auth_type": s.auth_type,
        "allowed_tools": s.allowed_tools or [],
        "discovered_tools": s.discovered_tools or [],
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


async def _get_server(server_id: str, user: User, db: AsyncSession) -> MCPServer:
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.user_id == user.id,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return server


@router.post("/servers")
async def register_mcp_server(
    body: MCPServerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Register an external MCP server."""
    encrypted_key = None
    if body.api_key:
        from credentials.encryption import encrypt_credential
        from core.config import settings
        encrypted_key = encrypt_credential(
            {"api_key": body.api_key},
            settings.APP_SECRET_KEY,
        )

    server = MCPServer(
        user_id=user.id,
        org_id=user.org_id,
        name=body.name,
        url=body.url,
        auth_type=body.auth_type,
        api_key_encrypted=encrypted_key,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return _serialize(server)


@router.get("/servers")
async def list_mcp_servers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List registered MCP servers for this user/workspace."""
    result = await db.execute(
        select(MCPServer)
        .where(MCPServer.user_id == user.id)
        .order_by(MCPServer.created_at.desc())
    )
    servers = result.scalars().all()
    return {"servers": [_serialize(s) for s in servers]}


@router.delete("/servers/{server_id}")
async def delete_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove an MCP server registration."""
    server = await _get_server(server_id, user, db)
    await db.delete(server)
    await db.commit()
    return {"deleted": True, "id": server_id}


@router.post("/servers/{server_id}/connect")
async def connect_mcp_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Test connection to an MCP server and discover its tools/resources."""
    server = await _get_server(server_id, user, db)

    headers = {"Content-Type": "application/json"}
    if server.api_key_encrypted:
        from credentials.encryption import decrypt_credential
        from core.config import settings
        cred = decrypt_credential(server.api_key_encrypted, settings.APP_SECRET_KEY)
        api_key = cred.get("api_key", "")
        headers["Authorization"] = f"Bearer {api_key}"

    # MCP protocol: send tools/list request
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Try JSON-RPC tools/list
            rpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }
            r = await client.post(server.url, headers=headers, json=rpc_request)
            r.raise_for_status()
            response = r.json()

            tools = []
            if "result" in response:
                result_data = response["result"]
                if isinstance(result_data, dict) and "tools" in result_data:
                    tools = result_data["tools"]
                elif isinstance(result_data, list):
                    tools = result_data

            # Cache discovered tools
            server.discovered_tools = tools
            server.is_active = True
            await db.commit()

            return {
                "status": "connected",
                "tools_found": len(tools),
                "tools": tools,
            }

    except httpx.ConnectError:
        server.is_active = False
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Cannot connect to MCP server at {server.url}")
    except httpx.TimeoutException:
        server.is_active = False
        await db.commit()
        raise HTTPException(status_code=504, detail="MCP server connection timed out")
    except Exception as e:
        log.warning("mcp_connect_error", server_id=server_id, error=str(e))
        raise HTTPException(status_code=502, detail=f"MCP server error: {str(e)}")


@router.get("/servers/{server_id}/tools")
async def list_server_tools(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List available tools from this MCP server (from cache)."""
    server = await _get_server(server_id, user, db)
    tools = server.discovered_tools or []

    # Filter by allowed_tools if set
    allowed = server.allowed_tools or []
    if allowed:
        tools = [t for t in tools if t.get("name") in allowed]

    return {
        "server_id": server.id,
        "server_name": server.name,
        "tools": tools,
        "total": len(tools),
    }


@router.put("/servers/{server_id}/permissions")
async def update_server_permissions(
    server_id: str,
    body: MCPServerPermissions,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set which tools are allowed for this MCP server."""
    server = await _get_server(server_id, user, db)
    server.allowed_tools = body.allowed_tools
    await db.commit()
    return {
        "server_id": server.id,
        "allowed_tools": server.allowed_tools,
    }
