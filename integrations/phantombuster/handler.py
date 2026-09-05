"""
PhantomBuster web automation integration.

Auth: api_key via X-Phantombuster-Key header.

Credential fields:
  - api_key (str) : PhantomBuster API key.

Nodes:
  - phantombuster.launch_agent : Launch a PhantomBuster agent.
  - phantombuster.get_output   : Get the output/result of an agent execution.
  - phantombuster.list_agents  : List all agents in the account.
  - phantombuster.stop_agent   : Stop a running agent execution.

Base URL: https://api.phantombuster.com/api/v2/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.phantombuster.com/api/v2/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("PhantomBuster credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "X-Phantombuster-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=60.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"PhantomBuster API error {r.status_code}: {detail}")


@register_node("phantombuster.launch_agent")
async def launch_agent(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Launch a PhantomBuster agent.

    Config / input keys:
      - agent_id (str, required) : PhantomBuster agent ID.
      - arguments (dict|str)     : JSON arguments to pass to the agent.
      - output (str)             : "result-object" | "first-result-object" | "result-object-in-file".
                                   Default "result-object".
    """
    agent_id = config.get("agent_id") or input_data.get("agent_id")
    if not agent_id:
        raise ValueError("phantombuster.launch_agent requires 'agent_id'")

    arguments = config.get("arguments") or input_data.get("arguments")
    output = config.get("output") or input_data.get("output", "result-object")

    payload: dict = {"id": agent_id, "output": output}
    if arguments:
        if isinstance(arguments, dict):
            import json
            payload["arguments"] = json.dumps(arguments)
        else:
            payload["arguments"] = str(arguments)

    log.info("phantombuster.launch_agent", agent_id=agent_id)
    async with await _client(credential_id, db) as client:
        r = await client.post("agents/launch", json=payload)
        _raise_for_status(r)
        data = r.json()

    return {
        "agent_id": agent_id,
        "container_id": data.get("containerId"),
        "status": data.get("status"),
        "raw": data,
    }


@register_node("phantombuster.get_output")
async def get_output(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetch the output/result of a PhantomBuster agent execution.

    Config / input keys:
      - agent_id (str, required)     : PhantomBuster agent ID.
      - container_id (str)           : Specific container/execution ID. If omitted, returns last run.
      - with_output (bool)           : Include console output log. Default False.
    """
    agent_id = config.get("agent_id") or input_data.get("agent_id")
    if not agent_id:
        raise ValueError("phantombuster.get_output requires 'agent_id'")

    container_id = config.get("container_id") or input_data.get("container_id")
    with_output = str(config.get("with_output") or input_data.get("with_output", False)).lower() == "true"

    params: dict = {"id": agent_id}
    if with_output:
        params["withOutput"] = "true"

    log.info("phantombuster.get_output", agent_id=agent_id, container_id=container_id)
    async with await _client(credential_id, db) as client:
        if container_id:
            r = await client.get("containers/fetch-output", params={"id": container_id})
        else:
            r = await client.get("agents/fetch-output", params=params)
        _raise_for_status(r)
        data = r.json()

    return {
        "agent_id": agent_id,
        "container_id": container_id or data.get("containerId"),
        "status": data.get("status"),
        "output": data.get("output"),
        "result_object": data.get("resultObject"),
        "exit_code": data.get("exitCode"),
        "raw": data,
    }


@register_node("phantombuster.list_agents")
async def list_agents(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all PhantomBuster agents in the account.

    Config / input keys: none required.
    """
    log.info("phantombuster.list_agents")
    async with await _client(credential_id, db) as client:
        r = await client.get("agents/fetch-all")
        _raise_for_status(r)
        data = r.json()

    agents = data if isinstance(data, list) else data.get("agents", data.get("data", []))
    return {"agents": agents, "count": len(agents)}


@register_node("phantombuster.stop_agent")
async def stop_agent(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Stop a running PhantomBuster agent.

    Config / input keys:
      - agent_id (str, required) : PhantomBuster agent ID.
    """
    agent_id = config.get("agent_id") or input_data.get("agent_id")
    if not agent_id:
        raise ValueError("phantombuster.stop_agent requires 'agent_id'")

    log.info("phantombuster.stop_agent", agent_id=agent_id)
    async with await _client(credential_id, db) as client:
        r = await client.post("agents/abort", json={"id": agent_id})
        _raise_for_status(r)
        data = r.json()

    return {
        "agent_id": agent_id,
        "stopped": True,
        "raw": data,
    }
