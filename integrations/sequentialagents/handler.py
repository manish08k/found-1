"""
Sequential agent nodes — LangGraph-style stateful workflow execution.
Each node operates on a shared state dict, enabling complex multi-step
agent flows with branching, loops, and tool calls.

Nodes:
  - seqagent.start            — Start: initialize agent state
  - seqagent.end              — End: terminal node, extract final output
  - seqagent.state            — State: update state variables
  - seqagent.llm_node         — LLMNode: call LLM, store result in state
  - seqagent.tool_node        — ToolNode: execute tool, update state
  - seqagent.agent            — Agent: full ReAct agent node
  - seqagent.condition        — Condition: state-based routing
  - seqagent.condition_agent  — ConditionAgent: LLM-based routing
  - seqagent.custom_function  — CustomFunction: user code, update state
  - seqagent.loop             — Loop: iterate over list in state
  - seqagent.execute_flow     — ExecuteFlow: call sub-workflow
"""
import asyncio
import json
import math
import re
import concurrent.futures

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


async def _call_llm(provider: str, model: str, system: str, prompt: str,
                    max_tokens: int = 1024) -> str:
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


def _safe_eval(expr: str, context: dict):
    safe_builtins = {
        "True": True, "False": False, "None": None,
        "len": len, "str": str, "int": int, "float": float, "bool": bool,
        "list": list, "dict": dict, "abs": abs, "round": round,
        "min": min, "max": max, "sum": sum, "any": any, "all": all,
        "isinstance": isinstance, "math": math,
    }
    return eval(expr, {"__builtins__": safe_builtins}, dict(context))  # noqa: S307


# ─── Start ────────────────────────────────────────────────────────────────────

@register_node("seqagent.start")
async def seqagent_start(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Start node: initializes the sequential agent state. Merges configured
    initial state with input_data, providing the baseline for subsequent nodes.

    config:
      - agent_name: display name for this agent flow
      - initial_state: dict of initial state variables
      - input_keys: list of keys from input_data to include in state
    """
    agent_name = config.get("agent_name", "SequentialAgent")
    initial_state = dict(config.get("initial_state") or {})
    input_keys = config.get("input_keys") or []

    state = dict(initial_state)

    # Include specified input keys (or all if none specified)
    if input_keys:
        for key in input_keys:
            if key in input_data:
                state[key] = input_data[key]
    else:
        state.update({k: v for k, v in input_data.items() if not k.startswith("_")})

    state["_agent_name"] = agent_name
    state["_step"] = 0
    state["_history"] = []

    log.info("seqagent_start", agent=agent_name, initial_keys=list(state.keys()))
    return state


# ─── End ──────────────────────────────────────────────────────────────────────

@register_node("seqagent.end")
async def seqagent_end(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    End node: terminal node that extracts and formats the final output.

    config:
      - output_key: key to extract as primary output (default: return full state)
      - output_keys: list of keys to include in the final output
      - include_history: include execution history in output (default: False)
    """
    output_key = config.get("output_key")
    output_keys = config.get("output_keys") or []
    include_history = config.get("include_history", False)

    if output_key:
        result = {
            "output": input_data.get(output_key),
            "key": output_key,
        }
        if include_history:
            result["history"] = input_data.get("_history", [])
        return result

    if output_keys:
        result = {k: input_data.get(k) for k in output_keys}
        if include_history:
            result["history"] = input_data.get("_history", [])
        return result

    # Return everything except internal state keys
    result = {k: v for k, v in input_data.items() if not k.startswith("_")}
    if include_history:
        result["history"] = input_data.get("_history", [])
    return result


# ─── State ───────────────────────────────────────────────────────────────────

@register_node("seqagent.state")
async def seqagent_state(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    State management node: updates state variables using expressions or templates.

    config:
      - state_updates: dict of {key: value_or_expression}
                       Values support {{ template }} syntax and simple Python expressions.
      - append_to: {key: value} to append to list fields in state
      - delete_keys: list of keys to remove from state
    """
    state = dict(input_data)
    step = state.get("_step", 0) + 1
    state["_step"] = step

    # Apply updates
    updates = config.get("state_updates") or {}
    for key, value in updates.items():
        if isinstance(value, str):
            # Try template rendering first
            rendered = _render(value, state)
            # Then try expression evaluation
            try:
                state[key] = _safe_eval(rendered, state)
            except Exception:
                state[key] = rendered
        else:
            state[key] = value

    # Append to lists
    appends = config.get("append_to") or {}
    for key, value in appends.items():
        current = state.get(key, [])
        if not isinstance(current, list):
            current = [current]
        if isinstance(value, str):
            value = _render(value, state)
        current.append(value)
        state[key] = current

    # Delete keys
    delete_keys = config.get("delete_keys") or []
    for key in delete_keys:
        state.pop(key, None)

    # Track history
    history = state.get("_history", [])
    history.append({"step": step, "node": "state", "updates": list(updates.keys())})
    state["_history"] = history

    return state


# ─── LLMNode ─────────────────────────────────────────────────────────────────

@register_node("seqagent.llm_node")
async def seqagent_llm_node(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    LLM Node: calls an LLM and stores the result in state.

    config:
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - prompt_template: prompt with {{ state_key }} templates
      - system_prompt: system instructions
      - input_key: state key to use as input (default: use prompt_template)
      - output_key: state key to store LLM response (default: "llm_output")
      - max_tokens: max response length (default: 1024)
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    output_key = config.get("output_key", "llm_output")
    max_tokens = int(config.get("max_tokens", 1024))
    system_prompt = _render(config.get("system_prompt", "You are a helpful assistant."), input_data)

    # Build prompt
    prompt_template = config.get("prompt_template", "")
    input_key = config.get("input_key")

    if prompt_template:
        prompt = _render(prompt_template, input_data)
    elif input_key:
        prompt = str(input_data.get(input_key, ""))
    else:
        prompt = str(input_data.get("input") or input_data.get("query") or input_data.get("message", ""))

    if not prompt:
        raise ValueError("seqagent.llm_node requires 'prompt_template' or 'input_key'")

    response = await _call_llm(provider, model, system_prompt, prompt, max_tokens)

    state = dict(input_data)
    state[output_key] = response.strip()
    state["_step"] = state.get("_step", 0) + 1

    history = state.get("_history", [])
    history.append({
        "step": state["_step"],
        "node": "llm",
        "output_key": output_key,
        "provider": provider,
    })
    state["_history"] = history

    return state


# ─── ToolNode ─────────────────────────────────────────────────────────────────

@register_node("seqagent.tool_node")
async def seqagent_tool_node(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Tool Node: executes a registered tool and stores result in state.

    config:
      - tool_node_id: node ID to execute (e.g. "tool.calculator")
      - tool_config: config dict for the tool
      - input_mapping: {tool_input_key: state_key} for mapping state to tool input
      - output_key: state key for tool result (default: "tool_output")
    """
    tool_node_id = config.get("tool_node_id")
    if not tool_node_id:
        raise ValueError("seqagent.tool_node requires 'tool_node_id'")

    if tool_node_id not in NODE_HANDLERS:
        raise ValueError(f"seqagent.tool_node: unknown tool '{tool_node_id}'")

    output_key = config.get("output_key", "tool_output")
    tool_config = dict(config.get("tool_config") or {})
    input_mapping = config.get("input_mapping") or {}

    tool_input = {}
    for tool_key, state_key in input_mapping.items():
        if isinstance(state_key, str) and "{{" in state_key:
            tool_input[tool_key] = _render(state_key, input_data)
        else:
            tool_input[tool_key] = input_data.get(state_key, state_key)

    if not tool_input:
        tool_input = {k: v for k, v in input_data.items() if not k.startswith("_")}

    merged_config = {**tool_input, **tool_config}
    result = await NODE_HANDLERS[tool_node_id](merged_config, tool_input, credential_id, db)

    state = dict(input_data)
    state[output_key] = result
    state["_step"] = state.get("_step", 0) + 1

    history = state.get("_history", [])
    history.append({
        "step": state["_step"],
        "node": "tool",
        "tool": tool_node_id,
        "output_key": output_key,
    })
    state["_history"] = history

    return state


# ─── Agent ────────────────────────────────────────────────────────────────────

@register_node("seqagent.agent")
async def seqagent_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Agent node: full ReAct agent with tools within a sequential agent flow.
    Reads input from state and writes answer back to state.

    config:
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - tools: list of tool node IDs
      - input_key: state key for agent input (default: "input")
      - output_key: state key for agent answer (default: "agent_output")
      - system_prompt: agent system instructions
      - max_iterations: max ReAct iterations (default: 8)
    """
    input_key = config.get("input_key", "input")
    output_key = config.get("output_key", "agent_output")
    task = _render(
        config.get("input") or str(input_data.get(input_key, "")),
        input_data,
    )

    if not task:
        raise ValueError("seqagent.agent requires input from state or 'input' config")

    # Delegate to agent.react
    agent_config = {
        **config,
        "input": task,
    }

    if "agent.react" in NODE_HANDLERS:
        result = await NODE_HANDLERS["agent.react"](agent_config, input_data, credential_id, db)
        answer = result.get("answer", "")
    else:
        answer = await _call_llm(
            config.get("provider", "openai"),
            config.get("model", ""),
            config.get("system_prompt", "You are a helpful assistant."),
            task,
            int(config.get("max_tokens", 1024)),
        )

    state = dict(input_data)
    state[output_key] = answer
    state["_step"] = state.get("_step", 0) + 1
    return state


# ─── Condition ────────────────────────────────────────────────────────────────

@register_node("seqagent.condition")
async def seqagent_condition(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Condition node: routes sequential agent flow based on state evaluation.

    config:
      - condition: Python expression evaluated against state, or structured condition dict
      - true_branch: branch label for true case (default: "true")
      - false_branch: branch label for false case (default: "false")
    """
    condition = config.get("condition", "False")
    true_branch = config.get("true_branch", "true")
    false_branch = config.get("false_branch", "false")

    condition_met = False
    try:
        if isinstance(condition, dict):
            field = condition.get("field")
            operator = condition.get("operator", "equals")
            value = condition.get("value")
            item_val = input_data.get(field) if field else None
            op_map = {
                "equals": lambda a, b: a == b,
                "not_equals": lambda a, b: a != b,
                "greater_than": lambda a, b: float(a or 0) > float(b),
                "less_than": lambda a, b: float(a or 0) < float(b),
                "contains": lambda a, b: str(b) in str(a or ""),
                "is_empty": lambda a, b: not a,
                "is_not_empty": lambda a, b: bool(a),
                "is_true": lambda a, b: bool(a),
            }
            fn = op_map.get(operator, lambda a, b: False)
            condition_met = fn(item_val, value)
        elif isinstance(condition, str):
            rendered = _render(condition, input_data)
            try:
                condition_met = bool(_safe_eval(rendered, input_data))
            except Exception:
                condition_met = rendered.lower() not in ("false", "0", "", "none", "null")
        else:
            condition_met = bool(condition)
    except Exception as e:
        log.warning("seqagent_condition_error", error=str(e))
        condition_met = False

    return {
        **input_data,
        "branch": true_branch if condition_met else false_branch,
        "condition_result": condition_met,
        "_step": input_data.get("_step", 0) + 1,
    }


# ─── ConditionAgent ──────────────────────────────────────────────────────────

@register_node("seqagent.condition_agent")
async def seqagent_condition_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    ConditionAgent: uses LLM to determine which branch to take.

    config:
      - condition_description: natural language description of the routing decision
      - options: list of branch name strings (e.g. ["escalate", "resolve", "clarify"])
      - provider: openai | anthropic
      - model: LLM model
      - context_keys: state keys to include as context
      - output_key: where to store chosen branch (default: "branch")
    """
    condition_desc = config.get("condition_description", "Choose the best action")
    options = config.get("options") or ["true", "false"]
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    context_keys = config.get("context_keys") or []
    output_key = config.get("output_key", "branch")

    # Build context
    if context_keys:
        context = {k: input_data.get(k) for k in context_keys if k in input_data}
    else:
        context = {k: v for k, v in input_data.items() if not k.startswith("_")}

    options_str = ", ".join(f'"{o}"' for o in options)
    system = f"You choose the best option from a given list. Respond with ONLY the option name — no explanation."
    prompt = (
        f"Decision: {condition_desc}\n\n"
        f"Context:\n{json.dumps(context, default=str, indent=2)}\n\n"
        f"Choose ONE of these options: {options_str}\n\n"
        "Your choice:"
    )

    response = await _call_llm(provider, model, system, prompt, 50)
    chosen = response.strip().strip('"').strip("'")

    # Find best match
    chosen_lower = chosen.lower()
    matched = next(
        (o for o in options if o.lower() == chosen_lower),
        next((o for o in options if o.lower() in chosen_lower), options[0]),
    )

    return {
        **input_data,
        output_key: matched,
        "branch": matched,
        "condition_description": condition_desc,
        "_step": input_data.get("_step", 0) + 1,
    }


# ─── CustomFunction ──────────────────────────────────────────────────────────

@register_node("seqagent.custom_function")
async def seqagent_custom_function(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Custom function node: executes user-defined Python code on the agent state.

    config:
      - code: Python function definition. Function must accept state dict and return dict.
      - function_name: function to call (default: 'execute')
      - input_keys: state keys to pass to function (default: all)
      - output_key: merge result under this key (default: merge into state)
      - timeout: max execution seconds (default: 10)
    """
    code = config.get("code", "")
    function_name = config.get("function_name", "execute")
    input_keys = config.get("input_keys") or []
    output_key = config.get("output_key")
    timeout = float(config.get("timeout", 10))

    if not code:
        return dict(input_data)

    fn_input = {k: input_data[k] for k in input_keys if k in input_data} if input_keys else dict(input_data)

    safe_globals = {
        "__builtins__": {
            "print": print, "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "tuple": tuple,
            "range": range, "enumerate": enumerate, "zip": zip,
            "sorted": sorted, "min": min, "max": max, "sum": sum, "abs": abs,
            "any": any, "all": all, "isinstance": isinstance,
            "True": True, "False": False, "None": None,
            "ValueError": ValueError, "TypeError": TypeError,
        },
        "json": json, "re": re, "math": math,
    }

    def _run():
        local_ns = {}
        exec(code, safe_globals, local_ns)  # noqa: S102
        if function_name not in local_ns:
            raise ValueError(f"Function '{function_name}' not found in code")
        result = local_ns[function_name](fn_input)
        return result if isinstance(result, dict) else {"result": result}

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await asyncio.wait_for(
            loop.run_in_executor(pool, _run),
            timeout=timeout,
        )

    state = dict(input_data)
    if output_key:
        state[output_key] = result
    else:
        state.update(result)
    state["_step"] = state.get("_step", 0) + 1
    return state


# ─── Loop ─────────────────────────────────────────────────────────────────────

@register_node("seqagent.loop")
async def seqagent_loop(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Loop node: iterates over a list in state, providing loop control signals.
    The execution engine uses the loop_index and loop_done fields to drive iteration.

    config:
      - items_key: state key containing the list to iterate (default: "items")
      - item_key: state key for the current item (default: "current_item")
      - index_key: state key for current index (default: "loop_index")
      - max_iterations: safety limit (default: 100)
    """
    items_key = config.get("items_key", "items")
    item_key = config.get("item_key", "current_item")
    index_key = config.get("index_key", "loop_index")
    max_iterations = int(config.get("max_iterations", 100))

    items = input_data.get(items_key, [])
    if not isinstance(items, list):
        items = [items] if items else []

    current_index = input_data.get(index_key, 0)

    if current_index >= len(items) or current_index >= max_iterations:
        return {
            **input_data,
            "loop_done": True,
            "branch": "done",
            index_key: current_index,
            item_key: None,
        }

    current_item = items[current_index]
    return {
        **input_data,
        item_key: current_item,
        index_key: current_index + 1,
        "loop_done": False,
        "loop_remaining": len(items) - current_index - 1,
        "branch": "continue",
        "_step": input_data.get("_step", 0) + 1,
    }


# ─── ExecuteFlow ──────────────────────────────────────────────────────────────

@register_node("seqagent.execute_flow")
async def seqagent_execute_flow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    ExecuteFlow: executes another workflow as a sub-flow within the sequential agent.

    config:
      - workflow_id: ID of the workflow to execute
      - input_mapping: {sub_flow_key: state_key} for building sub-flow input
      - output_key: state key for sub-flow result (default: "sub_flow_result")
      - timeout: max wait seconds (default: 60)
    """
    # Delegate to the agentflow.execute_flow implementation
    if "agentflow.execute_flow" in NODE_HANDLERS:
        result = await NODE_HANDLERS["agentflow.execute_flow"](config, input_data, credential_id, db)
    else:
        workflow_id = config.get("workflow_id")
        result = {
            "workflow_id": workflow_id,
            "result": None,
            "status": "not_available",
            "error": "agentflow.execute_flow handler not available",
        }

    output_key = config.get("output_key", "sub_flow_result")
    state = dict(input_data)
    state[output_key] = result
    state["_step"] = state.get("_step", 0) + 1
    return state
