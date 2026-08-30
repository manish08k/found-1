"""
Advanced AgentFlow nodes — planner, router, memory, loops, parallel/sequential
agents, and tool caller.

These extend the existing agentflow handler (integrations/agentflow/handler.py)
with higher-level orchestration primitives for complex agent workflows.
"""
import asyncio
import json
import re
import uuid

import httpx
import structlog

from core.execution_engine import register_node, NODE_HANDLERS
from core.config import settings

log = structlog.get_logger(__name__)


def _render(template: str, data: dict) -> str:
    if not isinstance(template, str):
        return template

    def repl(m):
        path = m.group(1).strip().split(".")
        val = data
        for p in path:
            val = val.get(p) if isinstance(val, dict) else None
        return "" if val is None else (val if isinstance(val, str) else json.dumps(val))

    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, template)


async def _call_llm(provider: str, model: str, system: str, prompt: str, max_tokens: int = 1024) -> str:
    """Minimal LLM caller supporting openai and anthropic."""
    if provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY required")
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                json={
                    "model": model or "claude-3-5-haiku-20241022",
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]
    else:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY required")
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model or "gpt-4o-mini",
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]


def _pick_provider(config: dict) -> str:
    provider = config.get("provider", "auto")
    if provider == "auto":
        if settings.ANTHROPIC_API_KEY:
            return "anthropic"
        if settings.OPENAI_API_KEY:
            return "openai"
        raise ValueError("No AI provider configured")
    return provider


# ─── Planner ──────────────────────────────────────────────────────────────────

@register_node("agentflow.planner")
async def agentflow_planner(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    LLM-based task planner that breaks a high-level goal into subtasks.

    config:
      - goal: The high-level objective (supports {{ }} templates)
      - provider: openai | anthropic
      - model: LLM model name
      - max_subtasks: maximum number of subtasks (default 10)
      - context: additional context for planning
    """
    provider = _pick_provider(config)
    model = config.get("model", "")
    goal = _render(config.get("goal") or config.get("input", ""), input_data)
    if not goal:
        goal = json.dumps(input_data)
    max_subtasks = int(config.get("max_subtasks", 10))
    context = _render(config.get("context", ""), input_data)

    system = (
        "You are a task planner. Break down the given goal into a list of concrete subtasks.\n"
        "Respond with ONLY a JSON object:\n"
        '{"subtasks": [{"id": 1, "title": "...", "description": "...", "dependencies": []}], '
        '"summary": "brief plan summary"}\n'
        f"Maximum {max_subtasks} subtasks. Each subtask should be specific and actionable."
    )
    prompt = f"Goal: {goal}"
    if context:
        prompt += f"\n\nAdditional context: {context}"

    raw = await _call_llm(provider, model, system, prompt, 2048)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        plan = json.loads(cleaned)
    except json.JSONDecodeError:
        plan = {"subtasks": [{"id": 1, "title": goal, "description": raw}], "summary": raw}

    subtasks = plan.get("subtasks", [])[:max_subtasks]

    return {
        **input_data,
        "plan": plan,
        "subtasks": subtasks,
        "subtask_count": len(subtasks),
        "goal": goal,
        "summary": plan.get("summary", ""),
    }


# ─── Router ───────────────────────────────────────────────────────────────────

@register_node("agentflow.router")
async def agentflow_router(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Routes to different branches based on LLM decision.

    config:
      - routes: list of {"name": str, "description": str}
      - input: the input to route (supports {{ }} templates)
      - provider/model: LLM config
    """
    provider = _pick_provider(config)
    model = config.get("model", "")
    routes = config.get("routes", [])
    user_input = _render(config.get("input") or config.get("prompt", ""), input_data)
    if not user_input:
        user_input = json.dumps(input_data)

    if not routes:
        return {**input_data, "route": "default", "route_reason": "No routes configured"}

    route_descriptions = "\n".join(
        f"- {r['name']}: {r.get('description', 'No description')}" for r in routes
    )
    route_names = [r["name"] for r in routes]

    system = (
        "You are a routing agent. Given the input, decide which route to send it to.\n"
        "Respond with ONLY a JSON object: {\"route\": \"route_name\", \"reason\": \"...\"}\n"
        f"Available routes:\n{route_descriptions}\n\n"
        f"Valid route names: {route_names}"
    )
    prompt = f"Input to route:\n{user_input}"

    raw = await _call_llm(provider, model, system, prompt, 200)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        decision = json.loads(cleaned)
        route = decision.get("route", routes[0]["name"])
        reason = decision.get("reason", "")
    except json.JSONDecodeError:
        # Try to extract route name from raw response
        route = routes[0]["name"]
        for r in routes:
            if r["name"].lower() in raw.lower():
                route = r["name"]
                break
        reason = raw

    return {
        **input_data,
        "route": route,
        "route_reason": reason,
        "branch": route,
    }


# ─── Memory Read ─────────────────────────────────────────────────────────────

@register_node("agentflow.memory_read")
async def agentflow_memory_read(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Reads agent state from MemoryMessage store.

    config:
      - conversation_id: conversation key (supports {{ }})
      - max_messages: max messages to retrieve (default 20)
      - role_filter: only return messages with this role (optional)
    """
    from sqlalchemy import select
    from storage.models import MemoryMessage

    workflow_id = config.get("_workflow_id")
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id", "default")
    max_messages = int(config.get("max_messages", 20))
    role_filter = config.get("role_filter")

    if not workflow_id:
        return {**input_data, "memory": [], "memory_count": 0}

    stmt = (
        select(MemoryMessage)
        .where(
            MemoryMessage.workflow_id == workflow_id,
            MemoryMessage.conversation_id == conversation_id,
        )
        .order_by(MemoryMessage.created_at.desc())
        .limit(max_messages)
    )
    if role_filter:
        stmt = stmt.where(MemoryMessage.role == role_filter)

    result = await db.execute(stmt)
    messages = result.scalars().all()
    messages.reverse()  # chronological order

    memory = [
        {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
        for m in messages
    ]

    return {
        **input_data,
        "memory": memory,
        "memory_count": len(memory),
        "conversation_id": conversation_id,
    }


# ─── Memory Write ────────────────────────────────────────────────────────────

@register_node("agentflow.memory_write")
async def agentflow_memory_write(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Writes agent state to MemoryMessage store.

    config:
      - conversation_id: conversation key (supports {{ }})
      - role: message role (default "assistant")
      - content: message content (supports {{ }})
      - content_field: alternatively, take content from this input_data field
    """
    from storage.models import MemoryMessage

    workflow_id = config.get("_workflow_id")
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id", "default")
    role = config.get("role", "assistant")

    content = _render(config.get("content", ""), input_data)
    if not content:
        content_field = config.get("content_field", "text")
        content = input_data.get(content_field, "")
    if not content:
        content = json.dumps(input_data)

    if not workflow_id:
        return {**input_data, "memory_written": False, "error": "No workflow context"}

    msg = MemoryMessage(
        workflow_id=workflow_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(msg)

    return {
        **input_data,
        "memory_written": True,
        "conversation_id": conversation_id,
        "role": role,
    }


# ─── Parallel Agents ─────────────────────────────────────────────────────────

@register_node("agentflow.parallel_agents")
async def agentflow_parallel_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Runs multiple sub-workflows or agent nodes in parallel.

    config:
      - agents: list of {"node_id": str, "config": dict, "name": str}
      - merge_strategy: "merge" | "list" (default: "merge")
      - timeout: seconds for all agents (default 120)
    """
    agents = config.get("agents", [])
    merge_strategy = config.get("merge_strategy", "merge")
    timeout = float(config.get("timeout", 120))

    if not agents:
        return {**input_data, "parallel_results": [], "error": "No agents configured"}

    async def run_agent(agent_cfg: dict) -> dict:
        node_id = agent_cfg.get("node_id", "")
        agent_config = {**agent_cfg.get("config", {}), "input": json.dumps(input_data)}
        name = agent_cfg.get("name", node_id)

        if node_id not in NODE_HANDLERS:
            return {"name": name, "error": f"Node {node_id} not found", "output": None}

        try:
            result = await NODE_HANDLERS[node_id](agent_config, input_data, credential_id, db)
            return {"name": name, "output": result, "error": None}
        except Exception as e:
            return {"name": name, "output": None, "error": str(e)}

    tasks = [run_agent(a) for a in agents]
    try:
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
    except asyncio.TimeoutError:
        return {**input_data, "parallel_results": [], "error": "Parallel execution timed out"}

    # Process results
    processed = []
    for r in results:
        if isinstance(r, Exception):
            processed.append({"name": "unknown", "output": None, "error": str(r)})
        else:
            processed.append(r)

    if merge_strategy == "merge":
        merged = dict(input_data)
        for p in processed:
            if p.get("output") and isinstance(p["output"], dict):
                merged.update(p["output"])
        merged["parallel_results"] = processed
        merged["parallel_count"] = len(processed)
        return merged
    else:
        return {**input_data, "parallel_results": processed, "parallel_count": len(processed)}


# ─── Sequential Agents ────────────────────────────────────────────────────────

@register_node("agentflow.sequential_agents")
async def agentflow_sequential_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Runs sub-workflows or agent nodes in sequence, passing each output as input to the next.

    config:
      - agents: list of {"node_id": str, "config": dict, "name": str}
      - stop_on_error: bool (default True)
    """
    agents = config.get("agents", [])
    stop_on_error = config.get("stop_on_error", True)

    if not agents:
        return {**input_data, "sequential_results": [], "error": "No agents configured"}

    current_data = dict(input_data)
    results = []

    for agent_cfg in agents:
        node_id = agent_cfg.get("node_id", "")
        agent_config = {**agent_cfg.get("config", {})}
        name = agent_cfg.get("name", node_id)

        if node_id not in NODE_HANDLERS:
            entry = {"name": name, "error": f"Node {node_id} not found", "output": None}
            results.append(entry)
            if stop_on_error:
                break
            continue

        try:
            result = await NODE_HANDLERS[node_id](agent_config, current_data, credential_id, db)
            results.append({"name": name, "output": result, "error": None})
            if isinstance(result, dict):
                current_data = {**current_data, **result}
        except Exception as e:
            results.append({"name": name, "output": None, "error": str(e)})
            if stop_on_error:
                break

    return {
        **current_data,
        "sequential_results": results,
        "sequential_count": len(results),
    }


# ─── Tool Caller ─────────────────────────────────────────────────────────────

@register_node("agentflow.tool_caller")
async def agentflow_tool_caller(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Calls a registered tool by name with LLM-generated arguments.

    config:
      - tool_name: the registered node type to call (e.g. "tool.calculator")
      - task: description of what to do (supports {{ }})
      - provider/model: LLM config for generating tool arguments
      - tool_schema: optional JSON schema describing the tool's expected input
    """
    provider = _pick_provider(config)
    model = config.get("model", "")
    tool_name = config.get("tool_name", "")
    task = _render(config.get("task") or config.get("input", ""), input_data)
    tool_schema = config.get("tool_schema", {})

    if not tool_name:
        raise ValueError("agentflow.tool_caller requires 'tool_name'")
    if tool_name not in NODE_HANDLERS:
        raise ValueError(f"Tool '{tool_name}' not registered")

    if not task:
        task = json.dumps(input_data)

    # Use LLM to generate tool arguments
    schema_str = json.dumps(tool_schema) if tool_schema else "Any JSON object with relevant parameters"

    system = (
        f"You are a tool caller. Generate the correct input arguments for the '{tool_name}' tool.\n"
        f"Expected input schema: {schema_str}\n"
        "Respond with ONLY a valid JSON object containing the tool's input parameters."
    )
    prompt = f"Task: {task}\n\nGenerate the tool input:"

    raw = await _call_llm(provider, model, system, prompt, 500)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        tool_args = json.loads(cleaned)
    except json.JSONDecodeError:
        tool_args = {"input": raw}

    if not isinstance(tool_args, dict):
        tool_args = {"input": tool_args}

    # Call the tool
    try:
        result = await NODE_HANDLERS[tool_name](tool_args, tool_args, credential_id, db)
    except Exception as e:
        return {
            **input_data,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_result": None,
            "tool_error": str(e),
        }

    return {
        **input_data,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "tool_result": result,
    }
